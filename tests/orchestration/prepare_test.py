"""Tests for :func:`tqec.orchestration.prepare_batch`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import stim

import tqec.orchestration.prepare as prepare_module
from tqec.computation.block_graph import BlockGraph
from tqec.gallery.cnot import cnot
from tqec.gallery.memory import memory
from tqec.interop.batch import split_dae_batch
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.orchestration import (
    BatchConfig,
    BatchManifest,
    LogicalObservableSelection,
    ManifestUnit,
    UnitStatus,
    prepare_batch,
)
from tqec.orchestration.prepare import (
    _reject_duplicate_unit_keys,
    _resolve_observable_fillings,
)
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

DAE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "interop"
    / "collada"
    / "test_files"
    / "disjoint_y_gadgets.dae"
)

_EIGHT_IDS = tuple(f"s00_disjoint_y_gadgets_batch{i:02d}" for i in range(1, 9))


def test_prepare_eight_gadget_dae_yields_stable_ids(tmp_path: Path) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    first = prepare_batch([DAE_FIXTURE], config, tmp_path / "run_a")
    second = prepare_batch([DAE_FIXTURE], config, tmp_path / "run_b")

    first_ids = tuple(u.gadget_id for u in first.units)
    second_ids = tuple(u.gadget_id for u in second.units)
    assert first_ids == _EIGHT_IDS
    assert second_ids == _EIGHT_IDS
    # The fixed-bulk Y cube is unimplemented on this branch, so every gadget is a terminal
    # COMPILE_FAILED record rather than crashing the whole batch.
    assert all(u.status == UnitStatus.COMPILE_FAILED.value for u in first.units)
    assert all(u.terminal for u in first.units)


def test_prepare_routes_by_input_type(tmp_path: Path) -> None:
    # Turn one DAE gadget into a standalone .bgraph so the .bgraph route is exercised too.
    component = split_dae_batch(DAE_FIXTURE, tmp_path / "components")[0]
    graph = read_block_graph_from_dae_file(component)
    bgraph_path = tmp_path / "single_gadget.bgraph"
    graph.to_bgraph(bgraph_path)

    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    manifest = prepare_batch([DAE_FIXTURE, bgraph_path, memory(Basis.Z)], config, tmp_path / "run")

    sources = {u.source for u in manifest.units}
    assert sources == {"disjoint_y_gadgets.dae", "single_gadget.bgraph", "<in-memory>"}
    # The in-memory memory gadget is closed and compiles, reaching READY.
    memory_units = [u for u in manifest.units if u.source == "<in-memory>"]
    assert len(memory_units) == 1
    assert memory_units[0].status == UnitStatus.READY.value
    # The in-memory graph is the third input (index 2), so its id is namespaced ``s02_``.
    assert memory_units[0].gadget_id == "s02_logical_z_memory_experiment"


def test_prepare_records_and_prints_gadget_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    manifest = prepare_batch([DAE_FIXTURE, memory(Basis.Z)], config, tmp_path / "run")

    failed = [u for u in manifest.units if u.terminal]
    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    # Every DAE gadget is terminal; the independent memory gadget still reaches READY.
    assert len(failed) == 8
    assert len(ready) == 1
    assert all(u.notes for u in failed)

    stderr = capsys.readouterr().err
    assert stderr.count("FAILED [compile]") == 8
    assert "disjoint_y_gadgets_batch01: NotImplementedError" in stderr


def test_prepare_records_resolved_observables_and_derived_port_fill(
    tmp_path: Path,
) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    manifest = prepare_batch([cnot()], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    # CNOT has open ports. Its generator observables require two compatible
    # measurement settings, represented by two completed manifest gadgets.
    assert len(ready) == 2
    assert all(
        set(unit.derived_port_cube_kinds or {}) == set(cnot().ordered_ports) for unit in ready
    )
    assert all(unit.logical_observables for unit in ready)
    assert all(
        observable.surface_id and observable.area > 0
        for unit in ready
        for observable in unit.logical_observables
    )
    assert len({unit.gadget_id for unit in ready}) == 2
    assert all("_ports_" in unit.gadget_id for unit in ready)

    # The persisted graph is the completed graph used for compilation, not the
    # original open graph. A downstream scheduler can therefore inspect the exact scheme.
    assert manifest.run_dir is not None
    for unit in ready:
        assert unit.graph is not None
        assert BlockGraph.from_json(manifest.run_dir / unit.graph).num_ports == 0

    reloaded = BatchManifest.read(manifest.run_dir)
    assert [
        (unit.logical_observables, unit.derived_port_cube_kinds) for unit in reloaded.units
    ] == [(unit.logical_observables, unit.derived_port_cube_kinds) for unit in manifest.units]


def test_logical_observable_selection_modes_are_resolved() -> None:
    graph = cnot()

    all_fillings = _resolve_observable_fillings(
        "cnot", graph, BatchConfig(logical_observables="all")
    )
    assert sum(len(f.observables) for f in all_fillings) == 4

    possible_fillings = _resolve_observable_fillings(
        "cnot", graph, BatchConfig(logical_observables="all_possible")
    )
    assert sum(len(f.observables) for f in possible_fillings) == 15

    area_fillings = _resolve_observable_fillings(
        "cnot", graph, BatchConfig(logical_observables="area_minimized")
    )
    assert sum(len(f.observables) for f in area_fillings) == 4

    first_random = _resolve_observable_fillings(
        "cnot", graph, BatchConfig(logical_observables="random", random_seed=7)
    )
    second_random = _resolve_observable_fillings(
        "cnot", graph, BatchConfig(logical_observables="random", random_seed=7)
    )
    assert len(first_random) == 1
    assert first_random[0].resolved_observables == second_random[0].resolved_observables
    assert len(first_random[0].observables) == 1


def test_config_validates_logical_observable_selection() -> None:
    for selection in LogicalObservableSelection:
        BatchConfig(logical_observables=selection.value).validate()
    with pytest.raises(TQECError, match="logical_observables"):
        BatchConfig(logical_observables="unknown").validate()


def test_manifest_consumable_in_separate_process(tmp_path: Path) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    run_dir = tmp_path / "run"
    prepare_batch([DAE_FIXTURE], config, run_dir)

    # A scheduler reads the manifest with only its path, using nothing but the sinter-free
    # schema module--no recompile, and sinter is never imported.
    script = (
        "import sys\n"
        "from tqec.orchestration.schema import BatchManifest\n"
        f"m = BatchManifest.read(r'{run_dir}')\n"
        "assert 'sinter' not in sys.modules, 'reading a manifest must not import sinter'\n"
        "print(len(m.units), m.config.ks[0])\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.split() == ["8", "1"]


def test_manifest_round_trips_through_disk(tmp_path: Path) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    run_dir = tmp_path / "run"
    written = prepare_batch([memory(Basis.Z)], config, run_dir)

    reloaded = BatchManifest.read(run_dir)
    assert [u.gadget_id for u in reloaded.units] == [u.gadget_id for u in written.units]
    assert reloaded.config == written.config
    ready = next(u for u in reloaded.units if u.status == UnitStatus.READY.value)
    # The run-relative circuit path resolves against the manifest's run directory.
    assert reloaded.run_dir is not None
    assert (reloaded.run_dir / ready.circuits[1]).is_file()


def test_config_validation_rejects_no_stopping_condition(tmp_path: Path) -> None:
    config = BatchConfig(ks=(1,), max_shots=None, max_errors=None)
    with pytest.raises(TQECError, match="stopping condition"):
        prepare_batch([memory(Basis.Z)], config, tmp_path / "run")


@pytest.mark.parametrize("field", ["ks", "ps", "conventions", "noise_models", "decoders"])
def test_config_validation_rejects_empty_axis(field: str) -> None:
    config = BatchConfig(**{field: ()})
    with pytest.raises(TQECError, match=field):
        config.validate()


def test_config_validation_accepts_default() -> None:
    # The default config carries a usable max_shots, so it validates without an explicit override.
    BatchConfig().validate()


def test_port_only_component_is_skipped(tmp_path: Path) -> None:
    lonely = BlockGraph(name="lonely_port")
    lonely.add_cube(Position3D(0, 0, 0), "PORT", label="A")

    messages: list[str] = []
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    manifest = prepare_batch(
        [lonely, memory(Basis.Z)], config, tmp_path / "run", progress=messages.append
    )

    skipped = [u for u in manifest.units if u.status == UnitStatus.SKIPPED.value]
    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(skipped) == 1
    # A skipped unit is neither terminal (a failure) nor completed; it is simply set aside.
    assert not skipped[0].terminal
    assert "skipped" in skipped[0].notes
    assert any("Skipping" in m for m in messages)
    # The real memory primitive next to it (which merely could have open ports) still compiles.
    assert len(ready) == 1


def test_same_named_inputs_get_distinct_ids(tmp_path: Path) -> None:
    # Two identically named in-memory graphs must not overwrite each other: the per-input ordinal
    # namespaces their ids so both survive in one manifest.
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    manifest = prepare_batch([memory(Basis.Z), memory(Basis.Z)], config, tmp_path / "run")

    ids = [u.gadget_id for u in manifest.units]
    assert ids == ["s00_logical_z_memory_experiment", "s01_logical_z_memory_experiment"]
    assert len(set(ids)) == 2


def test_reject_duplicate_unit_keys_fails_fast() -> None:
    units = [
        ManifestUnit("dup", "src", "n", "fixed_bulk", UnitStatus.READY.value),
        ManifestUnit("dup", "src", "n", "fixed_bulk", UnitStatus.READY.value),
    ]
    with pytest.raises(TQECError, match="Duplicate orchestration unit"):
        _reject_duplicate_unit_keys(units)


class _StubCompiled:
    """A stand-in compiled graph whose circuit generation fails for selected ``k`` values."""

    def __init__(self, fail_ks: set[int]):
        self._fail_ks = fail_ks

    def generate_stim_circuit(self, k: int, manhattan_radius: int = 2) -> stim.Circuit:
        if k in self._fail_ks:
            raise TQECError(f"circuit generation boom for k={k}")
        return stim.Circuit("H 0")


def test_partial_k_failure_still_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # k=1 generates, k=2 fails: the unit keeps the k=1 circuit and stays READY rather than losing
    # the good work, but records the failed k in its notes and prints a FAILED [circuit] line.
    monkeypatch.setattr(prepare_module, "compile_block_graph", lambda *a, **k: _StubCompiled({2}))
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1, 2))
    manifest = prepare_batch([memory(Basis.Z)], config, tmp_path / "run")

    unit = next(u for u in manifest.units if u.source == "<in-memory>")
    assert unit.status == UnitStatus.READY.value
    assert set(unit.circuits) == {1}
    assert "k=2" in unit.notes
    assert "FAILED [circuit]" in capsys.readouterr().err


def test_all_k_failure_is_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Every k fails: no circuit is produced, so the unit is a terminal CIRCUIT_FAILED record that
    # carries the real error type through to the manifest.
    monkeypatch.setattr(
        prepare_module, "compile_block_graph", lambda *a, **k: _StubCompiled({1, 2})
    )
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1, 2))
    manifest = prepare_batch([memory(Basis.Z)], config, tmp_path / "run")

    unit = next(u for u in manifest.units if u.source == "<in-memory>")
    assert unit.status == UnitStatus.CIRCUIT_FAILED.value
    assert unit.terminal
    assert unit.circuits == {}
    assert unit.stage == "circuit"
    assert unit.error == "TQECError"
