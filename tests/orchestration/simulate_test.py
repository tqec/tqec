"""Tests for :func:`tqec.orchestration.simulate_batch`.

The real :func:`sinter.collect` is always mocked -- sampling is far too slow for a unit test,
and the orchestration contract (one flattened collect, metadata-based association, resume
forwarding, status derivation) is fully observable through the mock.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import sinter

import tqec.orchestration.simulate as simulate_module
from tqec.gallery.memory import memory
from tqec.orchestration import (
    AggregateStatus,
    BatchConfig,
    BatchManifest,
    UnitStatus,
    prepare_batch,
    simulate_batch,
)
from tqec.orchestration.models import BatchResult
from tqec.utils.enums import Basis


@pytest.fixture(scope="module")
def memory_manifest(tmp_path_factory: pytest.TempPathFactory) -> BatchManifest:
    """Prepare the closed memory gadget once (circuits for k=1,2) for the simulate tests."""
    run_dir = tmp_path_factory.mktemp("memory_run")
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1, 2), observables="auto")
    return prepare_batch([memory(Basis.Z)], config, run_dir)


def _with_config(manifest: BatchManifest, **overrides: Any) -> BatchManifest:
    """Return a copy of ``manifest`` whose config has the given fields overridden."""
    config = dataclasses.replace(manifest.config, **overrides)
    return BatchManifest(
        run_id=manifest.run_id,
        config=config,
        units=manifest.units,
        run_dir=manifest.run_dir,
    )


def _install_collect(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[dict[str, Any]], list[sinter.TaskStats]],
) -> dict[str, Any]:
    """Install a fake ``sinter.collect`` that records its kwargs and delegates to ``handler``."""
    record: dict[str, Any] = {"calls": 0, "kwargs": None}

    def fake_collect(**kwargs: Any) -> list[sinter.TaskStats]:
        record["calls"] += 1
        kwargs["tasks"] = list(kwargs["tasks"])
        record["kwargs"] = kwargs
        return handler(kwargs)

    monkeypatch.setattr(simulate_module.sinter, "collect", fake_collect)
    return record


def _stats_for(
    task: sinter.Task,
    decoder: str,
    *,
    shots: int = 100,
    errors: int = 1,
    discards: int = 0,
    seconds: float = 0.1,
    strong_id: str | None = None,
) -> sinter.TaskStats:
    return sinter.TaskStats(
        strong_id=strong_id or f"{task.json_metadata['gadget_id']}-{task.json_metadata['k']}",
        decoder=decoder,
        json_metadata=task.json_metadata,
        shots=shots,
        errors=errors,
        discards=discards,
        seconds=seconds,
    )


def test_all_tasks_reach_one_sinter_collect(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _with_config(
        memory_manifest,
        ks=(1, 2),
        ps=(1e-3, 2e-3),
        noise_models=("uniform_depolarizing",),
        decoders=("pymatching", "fusion_blossom"),
    )

    def handler(kwargs: dict[str, Any]) -> list[sinter.TaskStats]:
        return [_stats_for(t, d) for t in kwargs["tasks"] for d in kwargs["decoders"]]

    record = _install_collect(monkeypatch, handler)
    simulate_batch(manifest)

    assert record["calls"] == 1
    tasks = record["kwargs"]["tasks"]
    # gadgets(1) x convention(1) x k(2) x noise(1) x p(2) = 4 tasks.
    assert len(tasks) == 4
    assert all(t.decoder is None for t in tasks)
    assert record["kwargs"]["decoders"] == ["pymatching", "fusion_blossom"]
    # Effective sampling cases are tasks x decoders.
    effective = len(tasks) * len(manifest.config.decoders)
    assert effective == 8


def test_stats_map_to_gadget_via_metadata(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _with_config(memory_manifest, ks=(1, 2), ps=(1e-3,), decoders=("pymatching",))

    def handler(kwargs: dict[str, Any]) -> list[sinter.TaskStats]:
        # Encode k into the error count so association can be checked independent of order.
        stats = [
            _stats_for(t, "pymatching", errors=10 * int(t.json_metadata["k"]))
            for t in kwargs["tasks"]
        ]
        random.Random(0).shuffle(stats)
        return stats

    _install_collect(monkeypatch, handler)
    result = simulate_batch(manifest)

    by_k = {r.k: r for r in result.results}
    assert set(by_k) == {1, 2}
    for k, r in by_k.items():
        assert r.gadget_id == "logical_z_memory_experiment"
        assert r.noise_model == "uniform_depolarizing"
        assert r.p == 1e-3
        assert r.decoder == "pymatching"
        assert r.d == 2 * k + 1
        assert r.errors == 10 * k  # proves association by metadata, not by order


def test_zero_errors_is_completed(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    # simulate samples every prepared circuit on disk (k=1 and k=2 from the fixture).
    manifest = _with_config(memory_manifest, ps=(1e-3,), decoders=("pymatching",))
    _install_collect(
        monkeypatch,
        lambda kw: [_stats_for(t, "pymatching", shots=1000, errors=0) for t in kw["tasks"]],
    )
    result = simulate_batch(manifest)

    assert len(result.results) == 2
    assert all(r.errors == 0 for r in result.results)
    assert all(r.status == UnitStatus.COMPLETED.value for r in result.results)
    assert result.aggregate == AggregateStatus.SUCCESS.value


def test_multiple_batches_combine_by_strong_id(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _with_config(memory_manifest, ps=(1e-3,), decoders=("pymatching",))

    def handler(kwargs: dict[str, Any]) -> list[sinter.TaskStats]:
        # Two rows for each effective case -- as incremental/resumed collection produces. The
        # strong id is per (case, decoder); different k are different cases and stay separate.
        rows = []
        for t in kwargs["tasks"]:
            sid = f"sid-{t.json_metadata['k']}"
            rows.append(_stats_for(t, "pymatching", shots=40, errors=1, seconds=0.2, strong_id=sid))
            rows.append(_stats_for(t, "pymatching", shots=60, errors=3, seconds=0.3, strong_id=sid))
        return rows

    _install_collect(monkeypatch, handler)
    result = simulate_batch(manifest)

    assert len(result.results) == 2
    for combined in result.results:
        assert combined.shots == 100
        assert combined.errors == 4
        assert combined.seconds == pytest.approx(0.5)


def test_partial_failure_status(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _with_config(memory_manifest, ks=(1, 2), ps=(1e-3,), decoders=("pymatching",))

    def handler(kwargs: dict[str, Any]) -> list[sinter.TaskStats]:
        # Return stats only for the k=1 case; k=2 gets none and becomes SIMULATION_FAILED.
        return [
            _stats_for(t, "pymatching") for t in kwargs["tasks"] if int(t.json_metadata["k"]) == 1
        ]

    _install_collect(monkeypatch, handler)
    result = simulate_batch(manifest)

    assert len(result.results) == 1
    assert result.results[0].k == 1
    assert len(result.failures) == 1
    assert result.failures[0].stage == "simulate"
    assert result.aggregate == AggregateStatus.PARTIAL_FAILURE.value


def test_resume_forwards_paths_and_continues(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _with_config(memory_manifest, ks=(1,), ps=(1e-3,), decoders=("pymatching",))
    resume = tmp_path / "resume.csv"
    existing = tmp_path / "existing.csv"

    record = _install_collect(
        monkeypatch, lambda kw: [_stats_for(t, "pymatching") for t in kw["tasks"]]
    )
    simulate_batch(
        manifest,
        save_resume_filepath=resume,
        existing_data_filepaths=[existing],
    )

    # The resume path and existing-data files are forwarded straight to sinter, which owns the
    # strong-id-based deduplication that keeps a resumed run from starting over.
    assert record["kwargs"]["save_resume_filepath"] == resume
    assert record["kwargs"]["existing_data_filepaths"] == [existing]


def test_results_written_atomically_and_reloadable(
    memory_manifest: BatchManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _with_config(memory_manifest, ks=(1,), ps=(1e-3,), decoders=("pymatching",))
    _install_collect(monkeypatch, lambda kw: [_stats_for(t, "pymatching") for t in kw["tasks"]])
    result = simulate_batch(manifest)

    assert manifest.run_dir is not None
    reloaded = BatchResult.read(manifest.run_dir)
    assert reloaded.aggregate == result.aggregate
    assert [r.strong_id for r in reloaded.results] == [r.strong_id for r in result.results]
