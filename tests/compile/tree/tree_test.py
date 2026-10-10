import warnings
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
    outdated_version = semver.Version(0, 1, 0)
    database.version = outdated_version
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

    # Running a second time should not emit any warning
    tree2 = compile_block_graph(g, observables=None).to_layer_tree()
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        circuit2 = tree2.generate_circuit(1, database_path=database_path)
    circuit2.detector_error_model()
    tqec_warnings = [w for w in record if issubclass(w.category, TQECWarning)]
    assert len(tqec_warnings) == 0


@pytest.mark.parametrize("suffix", ["json", "pkl"])
def test_custom_detector_database_with_old_version_is_rejected(tmp_path: Path, suffix: str) -> None:
    database_path = tmp_path / f"detectors.{suffix}"
    database = DetectorDatabase()
    outdated_version = semver.Version(0, 1, 0)
    database.version = outdated_version
    database.to_file(database_path)

    g = BlockGraph("Memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    tree = compile_block_graph(g, observables=None).to_layer_tree()
    with pytest.raises(TQECError, match="incompatible"):
        tree.generate_circuit(1, database_path=database_path)
    assert DetectorDatabase.from_file(database_path).version == outdated_version


@pytest.mark.parametrize("outdated_version", [semver.Version(0, 1, 0), semver.Version(0, 2, 0)])
def test_user_supplied_detector_database_with_old_version_is_rejected(
    outdated_version: semver.Version,
) -> None:
    database = DetectorDatabase()
    database.version = outdated_version

    g = BlockGraph("Memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    tree = compile_block_graph(g, observables=None).to_layer_tree()

    # When database_path is None
    with pytest.raises(TQECError, match="The provided detector_database is incompatible"):
        tree.generate_circuit(1, detector_database=database, database_path=None)

    # When database_path is default
    with pytest.raises(TQECError, match="The provided detector_database is incompatible"):
        tree.generate_circuit(1, detector_database=database)

    # Instance should remain unmodified
    assert database.version == outdated_version
