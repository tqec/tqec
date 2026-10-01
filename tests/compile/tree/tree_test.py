from pathlib import Path

import pytest
import semver

import tqec.compile.tree.tree as tree_mod
from tqec import BlockGraph, compile_block_graph
from tqec.compile.detectors.database import CURRENT_DATABASE_VERSION, DetectorDatabase
from tqec.utils.exceptions import TQECError, TQECWarning
from tqec.utils.position import Position3D


@pytest.mark.parametrize("suffix", ["json", "pkl"])
def test_default_detector_database_is_regenerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    database_path = tmp_path / f"detectors.{suffix}"
    database = DetectorDatabase(frozen=True)
    database.version = semver.Version(1, 0, 0)
    database.to_file(database_path)
    monkeypatch.setattr(tree_mod, "DEFAULT_DETECTOR_DATABASE_PATH", database_path)
    monkeypatch.setattr(tree_mod, "cpu_count", lambda: 1)

    g = BlockGraph("Memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    tree = compile_block_graph(g, observables=None).to_layer_tree()
    with pytest.warns(TQECWarning, match="out of date"):
        circuit = tree.generate_circuit(1, database_path=database_path)
    circuit.detector_error_model()

    regenerated = DetectorDatabase.from_file(database_path)
    assert regenerated.version == CURRENT_DATABASE_VERSION
    assert not regenerated.frozen
    assert len(regenerated) > 0


@pytest.mark.parametrize("suffix", ["json", "pkl"])
def test_custom_detector_database_with_old_version_is_rejected(tmp_path: Path, suffix: str) -> None:
    database_path = tmp_path / f"detectors.{suffix}"
    database = DetectorDatabase()
    database.version = semver.Version(1, 0, 0)
    database.to_file(database_path)

    g = BlockGraph("Memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    tree = compile_block_graph(g, observables=None).to_layer_tree()
    with pytest.raises(TQECError, match="incompatible"):
        tree.generate_circuit(1, database_path=database_path)
    assert DetectorDatabase.from_file(database_path).version == semver.Version(1, 0, 0)
