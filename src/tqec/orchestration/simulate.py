"""Stage 2: apply noise to prepared circuits and sample them in one ``sinter.collect``.

:func:`simulate_batch` reads a ``manifest.json`` (strategy (b): it never recompiles), loads each
prepared noiseless ``.stim`` off disk, applies the configured noise models, and flattens every
``gadget x convention x k x noise_model x p`` combination into a single task iterable handed to
one :func:`sinter.collect`. Running a single ``collect`` over the whole batch shares one worker
pool across every gadget instead of spinning one up per gadget.

Returned :class:`sinter.TaskStats` are mapped back to gadgets purely by their JSON metadata (and
the resolved decoder on the stats), never by order or filename. This is the only module in the
package that imports :mod:`sinter`.
"""

from __future__ import annotations

import multiprocessing
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

import sinter
import stim

from tqec.orchestration.models import (
    BatchConfig,
    BatchFailure,
    BatchManifest,
    BatchResult,
    ManifestUnit,
    UnitResult,
    UnitStatus,
    aggregate_status,
)
from tqec.utils.noise_model import NoiseModel

# Noise-model names resolve through this map, mirroring gadgetTesting's ``_NOISE_FACTORIES``.
NOISE_FACTORIES: dict[str, Callable[[float], NoiseModel]] = {
    "uniform_depolarizing": NoiseModel.uniform_depolarizing,
    "si1000": NoiseModel.si1000,
}


def simulate_batch(
    manifest_or_path: BatchManifest | str | Path,
    *,
    save_resume_filepath: str | Path | None = None,
    existing_data_filepaths: Iterable[str | Path] = (),
    progress: Callable[[sinter.Progress], None] | None = None,
    num_workers: int | None = None,
    custom_decoders: Mapping[str, sinter.Decoder | sinter.Sampler] | None = None,
    print_progress: bool = False,
) -> BatchResult:
    """Sample every prepared circuit in a batch through a single ``sinter.collect``.

    Args:
        manifest_or_path: A :class:`BatchManifest`, a path to ``manifest.json``, or the run
            directory containing it. When a path is given it is read fresh from disk.
        save_resume_filepath: Forwarded to :func:`sinter.collect`. When set, statistics are saved
            there as they are collected and reloaded on a later call with the same path, so a
            killed run resumes from the recorded totals instead of starting over.
        existing_data_filepaths: Forwarded to :func:`sinter.collect`. Statistics in these CSV
            files are loaded, returned, and counted towards ``max_shots``/``max_errors``.
        progress: An optional :class:`sinter.Progress` callback forwarded to ``collect``.
        num_workers: Worker process count. Defaults to :func:`multiprocessing.cpu_count`.
        custom_decoders: Optional mapping of decoder/sampler name to implementation, forwarded to
            ``collect`` without being serialized into any manifest.
        print_progress: Forwarded to :func:`sinter.collect` to print a live progress bar.

    Returns:
        A :class:`BatchResult`: one :class:`UnitResult` per effective ``(case, decoder)`` sampled,
        one :class:`BatchFailure` per prepared case that produced no usable statistics, and an
        aggregate outcome. Also written to ``results.json`` in the run directory.

    """
    manifest = (
        manifest_or_path
        if isinstance(manifest_or_path, BatchManifest)
        else BatchManifest.read(manifest_or_path)
    )
    run_dir = manifest.run_dir
    if run_dir is None:
        raise ValueError("The manifest has no run directory; cannot resolve prepared circuits.")

    config = manifest.config
    workers = multiprocessing.cpu_count() if num_workers is None else num_workers

    # Every expected (case) is a prepared circuit keyed by its authoritative metadata. Building
    # the list up front lets the returned stats be matched back and the missing ones reported.
    cases = list(_iter_cases(manifest, run_dir))
    tasks = [case.task for case in cases]

    stats = sinter.collect(
        num_workers=workers,
        tasks=tasks,
        decoders=list(config.decoders),
        existing_data_filepaths=[Path(p) for p in existing_data_filepaths],
        save_resume_filepath=None if save_resume_filepath is None else Path(save_resume_filepath),
        progress_callback=progress,
        max_shots=config.max_shots,
        max_errors=config.max_errors,
        max_batch_size=config.max_batch_size,
        max_batch_seconds=config.max_batch_seconds,
        custom_decoders=dict(custom_decoders) if custom_decoders else None,
        print_progress=print_progress,
        hint_num_tasks=len(tasks),
    )

    results, failures = _collate(cases, stats, config)
    for failure in failures:
        print(str(failure), file=sys.stderr)
    completed = sum(1 for r in results if r.status == UnitStatus.COMPLETED.value)
    aggregate = aggregate_status(completed, len(failures))
    result = BatchResult(
        run_id=manifest.run_id,
        results=results,
        failures=failures,
        aggregate=aggregate.value,
        run_dir=run_dir,
    )
    result.write(run_dir)
    return result


class _Case:
    """One prepared circuit expanded into a sinter task, keyed by its authoritative metadata."""

    def __init__(self, unit: ManifestUnit, k: int, noise_model: str, p: float, task: sinter.Task):
        self.unit = unit
        self.k = k
        self.noise_model = noise_model
        self.p = p
        self.task = task

    @property
    def key(self) -> tuple[str, str, int, str, float]:
        """Return the metadata key used to associate returned stats back to this case."""
        return (self.unit.gadget_id, self.unit.convention, self.k, self.noise_model, self.p)


def _iter_cases(manifest: BatchManifest, run_dir: Path) -> Iterator[_Case]:
    """Flatten every ``READY`` unit into ``gadget x k x noise_model x p`` sinter tasks.

    The task's ``decoder`` is left ``None`` so ``sinter.collect(decoders=...)`` expands each task
    across the configured decoders. Terminal (never-compiled) units are skipped here; they are
    carried in the manifest, not simulated.
    """
    config = manifest.config
    for unit in manifest.units:
        if unit.status != UnitStatus.READY.value:
            continue
        for k, rel_path in sorted(unit.circuits.items()):
            noiseless = stim.Circuit.from_file(run_dir / rel_path)
            for noise_model in config.noise_models:
                factory = _noise_factory(noise_model)
                for p in config.ps:
                    noisy = _apply_noise(noiseless, noise_model, factory, p)
                    metadata = {
                        "gadget_id": unit.gadget_id,
                        "source": unit.source,
                        "convention": unit.convention,
                        "noise_model": noise_model,
                        "k": k,
                        "d": 2 * k + 1,
                        "p": p,
                    }
                    task = sinter.Task(circuit=noisy, json_metadata=metadata)
                    yield _Case(unit, k, noise_model, p, task)


def _apply_noise(
    circuit: stim.Circuit,
    noise_model: str,
    factory: Callable[[float], NoiseModel],
    p: float,
) -> stim.Circuit:
    """Apply the named noise model to a noiseless detector-annotated circuit.

    ``si1000`` only supports Z-basis resets/measurements, so the circuit is first transpiled into
    its Z-basis gate set; the detectors and observables survive the transpile. ``uniform_
    depolarizing`` needs no transpile.
    """
    scored = circuit
    if noise_model == "si1000":
        from tqec.utils.noise_transpilation import transpile_to_si1000_gateset  # noqa: PLC0415

        scored = transpile_to_si1000_gateset(circuit)
    return factory(p).noisy_circuit(scored)


def _noise_factory(name: str) -> Callable[[float], NoiseModel]:
    """Resolve a noise-model name to its factory, failing fast on an unknown name."""
    try:
        return NOISE_FACTORIES[name]
    except KeyError:
        raise ValueError(
            f"Unknown noise model {name!r}. Supported: {', '.join(sorted(NOISE_FACTORIES))}."
        ) from None


def _collate(
    cases: list[_Case],
    stats: list[sinter.TaskStats],
    config: BatchConfig,
) -> tuple[list[UnitResult], list[BatchFailure]]:
    """Associate returned stats with cases by metadata, combining rows that share a strong id.

    Every expected ``(case, decoder)`` is accounted for: a case with matching stats becomes one or
    more :class:`UnitResult` (one per decoder), and one with no usable stats becomes a
    :class:`BatchFailure`. Several ``TaskStats`` rows for one ``(case, decoder)`` -- possible with
    incremental/resume collection -- are merged before a result is built.
    """
    case_by_key = {case.key: case for case in cases}

    # Accumulate stats per (case key, decoder), combining rows that share the effective case.
    merged: dict[tuple[tuple[str, str, int, str, float], str], _Accumulator] = {}
    for row in stats:
        key = _metadata_key(row.json_metadata)
        if key is None or key not in case_by_key:
            continue
        acc = merged.setdefault((key, row.decoder), _Accumulator(row.decoder, row.strong_id))
        acc.add(row)

    results: list[UnitResult] = []
    failures: list[BatchFailure] = []
    for case in cases:
        got_any = False
        for decoder in config.decoders:
            acc = merged.get((case.key, decoder))
            if acc is None:
                continue
            got_any = True
            results.append(_unit_result(case, acc))
        if not got_any:
            failures.append(
                BatchFailure(
                    gadget_id=case.unit.gadget_id,
                    stage="simulate",
                    error="NoStatistics",
                    message=(
                        f"no statistics for k={case.k} {case.noise_model} p={case.p} "
                        f"[{case.unit.convention}]"
                    ),
                )
            )
    return results, failures


class _Accumulator:
    """Sums the sampling counts of every ``TaskStats`` row sharing one effective case."""

    def __init__(self, decoder: str, strong_id: str):
        self.decoder = decoder
        self.strong_id = strong_id
        self.shots = 0
        self.errors = 0
        self.discards = 0
        self.seconds = 0.0
        self.custom_counts: dict[str, int] = {}

    def add(self, row: sinter.TaskStats) -> None:
        """Fold one stats row into the running totals."""
        self.shots += row.shots
        self.errors += row.errors
        self.discards += row.discards
        self.seconds += row.seconds
        for name, value in dict(row.custom_counts).items():
            self.custom_counts[name] = self.custom_counts.get(name, 0) + value


def _unit_result(case: _Case, acc: _Accumulator) -> UnitResult:
    """Build a :class:`UnitResult` for one case and its merged stats.

    Zero errors with nonzero shots is a valid ``COMPLETED`` result; ``SIMULATION_FAILED`` is only
    for cases that collected no shots at all.
    """
    status = UnitStatus.COMPLETED if acc.shots > 0 else UnitStatus.SIMULATION_FAILED
    return UnitResult(
        gadget_id=case.unit.gadget_id,
        source=case.unit.source,
        convention=case.unit.convention,
        k=case.k,
        d=2 * case.k + 1,
        noise_model=case.noise_model,
        p=case.p,
        decoder=acc.decoder,
        shots=acc.shots,
        errors=acc.errors,
        discards=acc.discards,
        seconds=acc.seconds,
        strong_id=acc.strong_id,
        status=status.value,
        custom_counts=acc.custom_counts,
    )


def _metadata_key(metadata: Any) -> tuple[str, str, int, str, float] | None:
    """Extract the association key from a task's JSON metadata, or ``None`` if it is not ours."""
    if not isinstance(metadata, Mapping):
        return None
    try:
        return (
            str(metadata["gadget_id"]),
            str(metadata["convention"]),
            int(metadata["k"]),
            str(metadata["noise_model"]),
            float(metadata["p"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
