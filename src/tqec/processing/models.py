"""On-disk schemas and value types shared by the ``tqec.processing`` batch stages.

The batch pipeline is deliberately split into two independently runnable stages that
communicate only through run-directory files::

    prepare  -> manifest.json   (what was built: noiseless circuits + per-gadget metadata)
    simulate -> results.json    (what was measured: sampled statistics per case)

This module owns the two schemas and their (de)serialization. It imports only the standard
library and typing, so a scheduler process can read a ``manifest.json`` -- to inspect what a
prepare produced, or to hand work out -- without importing :mod:`sinter`, :mod:`collada`, or
any heavy ``tqec`` machinery.

Artifact paths inside :class:`ManifestUnit` are stored relative to the run directory so a run
can be moved or copied between machines, which matters when the two stages run as separate
scheduler jobs on a shared filesystem. The run directory itself is carried on
:class:`BatchManifest` (:attr:`BatchManifest.run_dir`), never written into the JSON, since it
is simply the location the file was read from or written to.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
RESULTS_NAME = "results.json"


class UnitStatus(str, Enum):
    """Lifecycle state of one prepared gadget.

    The members are ordered so that "furthest reached" is monotone: a gadget walks the
    terminal failure states in the order it can hit them (import, validate, observable,
    compile, circuit) before reaching :attr:`READY`, and a simulated unit ends at
    :attr:`COMPLETED` or :attr:`SIMULATION_FAILED`.
    """

    IMPORT_FAILED = "import_failed"
    INVALID_GRAPH = "invalid_graph"
    OBSERVABLE_FAILED = "observable_failed"
    COMPILE_FAILED = "compile_failed"
    CIRCUIT_FAILED = "circuit_failed"
    READY = "ready"
    COMPLETED = "completed"
    SIMULATION_FAILED = "simulation_failed"


# Statuses that mean compilation never produced a circuit for the unit. Such a unit is
# carried through to results unscored instead of being dropped, mirroring gadgetTesting's
# ``CircuitUnit.terminal``.
_TERMINAL_STATUS_VALUES = frozenset(
    {
        UnitStatus.IMPORT_FAILED.value,
        UnitStatus.INVALID_GRAPH.value,
        UnitStatus.OBSERVABLE_FAILED.value,
        UnitStatus.COMPILE_FAILED.value,
        UnitStatus.CIRCUIT_FAILED.value,
    }
)


class AggregateStatus(str, Enum):
    """Overall outcome of a batch run."""

    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


@dataclass(frozen=True)
class BatchConfig:
    """Scoring and generation parameters carried alongside a batch.

    Everything the simulate stage needs is recorded here so a scheduler job can simulate from
    ``manifest.json`` alone, without a separate config file. ``conventions`` and
    ``noise_models`` are keys into :data:`tqec.compile.convention.ALL_CONVENTIONS` and the
    ``NOISE_FACTORIES`` map in :mod:`tqec.processing.simulate` respectively.
    """

    conventions: tuple[str, ...] = ("fixed_bulk",)
    ks: tuple[int, ...] = (1, 2)
    ps: tuple[float, ...] = (1e-3,)
    noise_models: tuple[str, ...] = ("uniform_depolarizing",)
    decoders: tuple[str, ...] = ("pymatching",)
    manhattan_radius: int = 2
    observables: str = "minimal"
    max_shots: int | None = None
    max_errors: int | None = None
    max_batch_size: int | None = None
    max_batch_seconds: int | None = None
    expected_distance: str = "2*k + 1"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping of this config (tuples become lists)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchConfig:
        """Reconstruct a :class:`BatchConfig` from its serialized mapping."""
        defaults = cls()
        tuple_fields = ("conventions", "ks", "ps", "noise_models", "decoders")
        kwargs: dict[str, Any] = {}
        for name in (f.name for f in fields(cls)):
            if name not in data:
                kwargs[name] = getattr(defaults, name)
            elif name in tuple_fields:
                kwargs[name] = tuple(data[name])
            else:
                kwargs[name] = data[name]
        return cls(**kwargs)


@dataclass
class ManifestUnit:
    """One prepared gadget: a compiled graph plus its noiseless circuits.

    This is a superset of gadgetTesting's ``CircuitUnit`` so the harness ``ResultRow`` can
    remain a projection over it. There is one unit per ``(gadget, convention)``; a gadget with
    open ports that is filled for minimal simulation produces one unit per filling, each with a
    distinct :attr:`gadget_id` (a ``_fillNN`` suffix) and :attr:`fill_index`.

    Artifact paths (:attr:`circuits`, :attr:`graph`) are stored relative to the run directory;
    resolve them against :attr:`BatchManifest.run_dir`.
    """

    gadget_id: str
    source: str
    name: str
    convention: str
    status: str
    fill_index: int = 0
    observables: int = 0
    circuits: dict[int, str] = field(default_factory=dict)
    graph: str | None = None
    notes: str = ""

    @property
    def terminal(self) -> bool:
        """Whether compilation never produced a circuit for this unit."""
        return self.status in _TERMINAL_STATUS_VALUES

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping of this unit.

        Circuit keys (``k`` values) are emitted as strings because JSON object keys must be
        strings; :meth:`from_dict` restores them to integers.
        """
        return {
            "gadget_id": self.gadget_id,
            "source": self.source,
            "name": self.name,
            "convention": self.convention,
            "status": self.status,
            "fill_index": self.fill_index,
            "observables": self.observables,
            "circuits": {str(k): v for k, v in self.circuits.items()},
            "graph": self.graph,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestUnit:
        """Reconstruct a :class:`ManifestUnit` from its serialized mapping."""
        return cls(
            gadget_id=data["gadget_id"],
            source=data["source"],
            name=data["name"],
            convention=data["convention"],
            status=data["status"],
            fill_index=int(data.get("fill_index", 0)),
            observables=int(data.get("observables", 0)),
            circuits={int(k): v for k, v in data.get("circuits", {}).items()},
            graph=data.get("graph"),
            notes=data.get("notes", ""),
        )


@dataclass
class BatchManifest:
    """What a prepare produced: the config it ran under and one record per gadget.

    :attr:`run_dir` is the directory the manifest lives in; it is not part of the on-disk JSON
    (it is simply where the file was read from or written to) and is used to resolve the
    run-relative artifact paths on the units.
    """

    run_id: str
    config: BatchConfig
    units: list[ManifestUnit] = field(default_factory=list)
    run_dir: Path | None = None

    def write(self, run_dir: str | Path | None = None) -> Path:
        """Write ``manifest.json`` atomically and return its path.

        Args:
            run_dir: Directory to write into. Defaults to :attr:`run_dir`. Setting it here also
                updates :attr:`run_dir`.

        Returns:
            The path to the written ``manifest.json``.

        Raises:
            ValueError: If no run directory is available from the argument or :attr:`run_dir`.

        """
        target = Path(run_dir) if run_dir is not None else self.run_dir
        if target is None:
            raise ValueError("A run directory is required to write the manifest.")
        target.mkdir(parents=True, exist_ok=True)
        self.run_dir = target
        payload = {
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "units": [unit.to_dict() for unit in self.units],
        }
        return _atomic_write_json(target / MANIFEST_NAME, payload)

    @classmethod
    def read(cls, path_or_dir: str | Path) -> BatchManifest:
        """Read a ``manifest.json`` from a file path or its containing run directory."""
        path, run_dir = _resolve_artifact(path_or_dir, MANIFEST_NAME)
        data = json.loads(path.read_text())
        return cls(
            run_id=data.get("run_id", run_dir.name),
            config=BatchConfig.from_dict(data.get("config", {})),
            units=[ManifestUnit.from_dict(item) for item in data.get("units", [])],
            run_dir=run_dir,
        )


@dataclass(frozen=True)
class UnitResult:
    """One sampled case: a prepared gadget simulated under one ``(noise, p, decoder)``.

    Cases are associated back to their gadget by metadata (:attr:`gadget_id`, :attr:`convention`,
    :attr:`k`, :attr:`noise_model`, :attr:`p`) plus the decoder, never by order or filename.
    """

    gadget_id: str
    source: str
    convention: str
    k: int
    d: int
    noise_model: str
    p: float
    decoder: str
    shots: int
    errors: int
    discards: int
    seconds: float
    strong_id: str
    status: str
    custom_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping of this result."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnitResult:
        """Reconstruct a :class:`UnitResult` from its serialized mapping."""
        return cls(
            gadget_id=data["gadget_id"],
            source=data["source"],
            convention=data["convention"],
            k=int(data["k"]),
            d=int(data["d"]),
            noise_model=data["noise_model"],
            p=float(data["p"]),
            decoder=data["decoder"],
            shots=int(data["shots"]),
            errors=int(data["errors"]),
            discards=int(data["discards"]),
            seconds=float(data["seconds"]),
            strong_id=data["strong_id"],
            status=data["status"],
            custom_counts=dict(data.get("custom_counts", {})),
        )


@dataclass(frozen=True)
class BatchFailure:
    """One gadget that could not be prepared or simulated.

    Generalizes :class:`tqec.interop.batch.BatchImportFailure`: the import special case is
    ``stage="import"``. The string form matches the plain-text line printed to stderr.
    """

    gadget_id: str
    stage: str
    error: str
    message: str

    def __str__(self) -> str:
        return f"FAILED [{self.stage}] {self.gadget_id}: {self.error}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping of this failure."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchFailure:
        """Reconstruct a :class:`BatchFailure` from its serialized mapping."""
        return cls(
            gadget_id=data["gadget_id"],
            stage=data["stage"],
            error=data["error"],
            message=data["message"],
        )


@dataclass
class BatchResult:
    """What a simulate produced: sampled results, gadget failures, and an aggregate outcome."""

    run_id: str
    results: list[UnitResult] = field(default_factory=list)
    failures: list[BatchFailure] = field(default_factory=list)
    aggregate: str = AggregateStatus.SUCCESS.value
    run_dir: Path | None = None

    def write(self, run_dir: str | Path | None = None) -> Path:
        """Write ``results.json`` atomically and return its path.

        Args:
            run_dir: Directory to write into. Defaults to :attr:`run_dir`. Setting it here also
                updates :attr:`run_dir`.

        Returns:
            The path to the written ``results.json``.

        Raises:
            ValueError: If no run directory is available from the argument or :attr:`run_dir`.

        """
        target = Path(run_dir) if run_dir is not None else self.run_dir
        if target is None:
            raise ValueError("A run directory is required to write the results.")
        target.mkdir(parents=True, exist_ok=True)
        self.run_dir = target
        payload = {
            "run_id": self.run_id,
            "aggregate": self.aggregate,
            "results": [result.to_dict() for result in self.results],
            "failures": [failure.to_dict() for failure in self.failures],
        }
        return _atomic_write_json(target / RESULTS_NAME, payload)

    @classmethod
    def read(cls, path_or_dir: str | Path) -> BatchResult:
        """Read a ``results.json`` from a file path or its containing run directory."""
        path, run_dir = _resolve_artifact(path_or_dir, RESULTS_NAME)
        data = json.loads(path.read_text())
        return cls(
            run_id=data.get("run_id", run_dir.name),
            results=[UnitResult.from_dict(item) for item in data.get("results", [])],
            failures=[
                BatchFailure.from_dict(item) for item in data.get("failures", [])
            ],
            aggregate=data.get("aggregate", AggregateStatus.SUCCESS.value),
            run_dir=run_dir,
        )


def aggregate_status(
    completed: int, failed: int, *, run_level_error: bool = False
) -> AggregateStatus:
    """Combine per-unit outcomes into an :class:`AggregateStatus`.

    Args:
        completed: Number of units that reached :attr:`UnitStatus.COMPLETED`.
        failed: Number of units that failed at any stage.
        run_level_error: When ``True``, a run-level error prevented collection; the result is
            :attr:`AggregateStatus.FAILED` regardless of the counts.

    Returns:
        :attr:`AggregateStatus.SUCCESS` when every unit completed and none failed,
        :attr:`AggregateStatus.PARTIAL_FAILURE` when at least one completed and at least one
        failed, and :attr:`AggregateStatus.FAILED` otherwise.

    """
    if run_level_error or completed == 0:
        return AggregateStatus.FAILED
    if failed == 0:
        return AggregateStatus.SUCCESS
    return AggregateStatus.PARTIAL_FAILURE


def _atomic_write_json(path: Path, payload: Any) -> Path:
    """Write ``payload`` as JSON to ``path`` atomically (temp file + :func:`os.replace`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    os.replace(tmp, path)
    return path


def _resolve_artifact(path_or_dir: str | Path, filename: str) -> tuple[Path, Path]:
    """Resolve a schema artifact to ``(file_path, run_dir)``.

    ``path_or_dir`` may name the artifact file directly or the run directory that contains it.

    Raises:
        FileNotFoundError: If the artifact cannot be found.

    """
    candidate = Path(path_or_dir)
    if candidate.is_dir():
        path = candidate / filename
        run_dir = candidate
    else:
        path = candidate
        run_dir = candidate.parent
    if not path.is_file():
        raise FileNotFoundError(f"No {filename} found at {path}.")
    return path, run_dir
