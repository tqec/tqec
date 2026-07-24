"""Tests for :func:`tqec.processing.prepare_batch`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tqec.gallery.cnot import cnot
from tqec.gallery.memory import memory
from tqec.interop.batch import split_dae_batch
from tqec.interop.collada import read_block_graph_from_dae_file
from tqec.processing import BatchConfig, BatchManifest, UnitStatus, prepare_batch
from tqec.utils.enums import Basis

DAE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "interop"
    / "collada"
    / "test_files"
    / "disjoint_y_gadgets.dae"
)

_EIGHT_IDS = tuple(f"disjoint_y_gadgets_batch{i:02d}" for i in range(1, 9))


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

    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), observables="minimal")
    manifest = prepare_batch([DAE_FIXTURE, bgraph_path, memory(Basis.Z)], config, tmp_path / "run")

    sources = {u.source for u in manifest.units}
    assert sources == {"disjoint_y_gadgets.dae", "single_gadget.bgraph", "<in-memory>"}
    # The in-memory memory gadget is closed and compiles, reaching READY.
    memory_units = [u for u in manifest.units if u.source == "<in-memory>"]
    assert len(memory_units) == 1
    assert memory_units[0].status == UnitStatus.READY.value
    assert memory_units[0].gadget_id == "logical_z_memory_experiment"


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


def test_prepare_minimal_fill_keys_each_filling(tmp_path: Path) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), observables="minimal")
    manifest = prepare_batch([cnot()], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    # cnot has open ports; minimal fill yields two fillings, each its own unit.
    assert len(ready) == 2
    assert {u.gadget_id for u in ready} == {"logical_cnot_fill00", "logical_cnot_fill01"}
    assert {u.fill_index for u in ready} == {0, 1}


def test_manifest_consumable_in_separate_process(tmp_path: Path) -> None:
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,))
    run_dir = tmp_path / "run"
    prepare_batch([DAE_FIXTURE], config, run_dir)

    # A scheduler reads the manifest with only its path, using nothing but the sinter-free
    # models module -- no recompile, and sinter is never imported.
    script = (
        "import sys\n"
        "from tqec.processing.models import BatchManifest\n"
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
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), observables="auto")
    run_dir = tmp_path / "run"
    written = prepare_batch([memory(Basis.Z)], config, run_dir)

    reloaded = BatchManifest.read(run_dir)
    assert [u.gadget_id for u in reloaded.units] == [u.gadget_id for u in written.units]
    assert reloaded.config == written.config
    ready = next(u for u in reloaded.units if u.status == UnitStatus.READY.value)
    # The run-relative circuit path resolves against the manifest's run directory.
    assert reloaded.run_dir is not None
    assert (reloaded.run_dir / ready.circuits[1]).is_file()
