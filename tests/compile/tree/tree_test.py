import hashlib
import warnings
from pathlib import Path

import pytest
import semver

from tqec.compile.tree.tree import LayerTree
from tqec import BlockGraph, compile_block_graph
from tqec.compile.detectors.database import CURRENT_DATABASE_VERSION, DetectorDatabase
from tqec.utils.exceptions import TQECError, TQECWarning
from tqec.utils.position import Position3D


@pytest.fixture
def memory_tree() -> LayerTree:
    graph = BlockGraph("Memory")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    return compile_block_graph(graph, observables=None).to_layer_tree()


@pytest.mark.parametrize("suffix", ["json", "pkl"])
def test_default_detector_database_is_regenerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    database_path = tmp_path / f"detectors.{suffix}"
    database = DetectorDatabase(frozen=True)
    outdated_version = semver.Version(0, 1, 0)
    database.version = outdated_version
    database.to_file(database_path)
    monkeypatch.setattr("tqec.compile.tree.tree.DEFAULT_DETECTOR_DATABASE_PATH", database_path)
    monkeypatch.setattr("tqec.compile.tree.tree.cpu_count", lambda: 1)

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


@pytest.mark.parametrize(
    "suffix, contents",
    [
        (
            "json",
            b'{"mapping": [], "frozen": false, "uniq_plaquettes": [], "version": "invalid"}',
        ),
        ("json", b"{not-json"),
        ("pkl", b"not-a-pickle"),
    ],
)
def test_corrupt_custom_detector_database_is_preserved(
    tmp_path: Path, suffix: str, contents: bytes, memory_tree: LayerTree
) -> None:
    database_path = tmp_path / f"user_database.{suffix}"
    database_path.write_bytes(contents)

    with pytest.raises(TQECError, match="Could not load user-provided detector database"):
        memory_tree.generate_circuit(1, database_path=database_path)

    assert database_path.read_bytes() == contents
    assert list(tmp_path.glob("faulty_database_*")) == []


@pytest.mark.parametrize(
    "suffix, contents",
    [
        (
            "json",
            b'{"mapping": [], "frozen": false, "uniq_plaquettes": [], "version": "invalid"}',
        ),
        ("pkl", b"not-a-pickle"),
    ],
)
def test_corrupt_default_detector_database_can_be_regenerated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    contents: bytes,
    memory_tree: LayerTree,
) -> None:
    database_path = tmp_path / f"detectors.{suffix}"
    database_path.write_bytes(contents)
    monkeypatch.setattr("tqec.compile.tree.tree.DEFAULT_DETECTOR_DATABASE_PATH", database_path)
    monkeypatch.setattr("tqec.compile.tree.tree.cpu_count", lambda: 1)

    with pytest.warns(UserWarning, match="Moving the database"):
        circuit = memory_tree.generate_circuit(1, database_path=database_path)
    circuit.detector_error_model()

    assert database_path.exists()
    assert DetectorDatabase.from_file(database_path).version == CURRENT_DATABASE_VERSION
    moved_files = list(tmp_path.glob(f"faulty_database_*.{suffix}"))
    assert len(moved_files) == 1
    assert moved_files[0].read_bytes() == contents


def test_invalid_pickle_version_default_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, memory_tree: LayerTree
) -> None:
    path = tmp_path / "default.pkl"
    database = DetectorDatabase()
    database.version = "invalid"  # ty: ignore[invalid-assignment]
    database.to_file(path)
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr("tqec.compile.tree.tree.DEFAULT_DETECTOR_DATABASE_PATH", path)
    monkeypatch.setattr("tqec.compile.tree.tree.cpu_count", lambda: 1)
    with pytest.warns(UserWarning, match="Moving the database"):
        memory_tree.generate_circuit(1, database_path=path).detector_error_model()
    backups = list(tmp_path.glob("faulty_database_*.pkl"))
    assert len(backups) == 1
    assert hashlib.sha256(backups[0].read_bytes()).hexdigest() == original_hash
    assert DetectorDatabase.from_file(path).version == CURRENT_DATABASE_VERSION
