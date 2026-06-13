from pathlib import Path

import pytest
import semver

from tqec.compile.compile import _DEFAULT_BLOCK_REPETITIONS, compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.compile.detectors.database import CURRENT_DATABASE_VERSION, DetectorDatabase
from tqec.computation.block_graph import BlockGraph
from tqec.utils.exceptions import TQECWarning
from tqec.utils.position import Position3D


def test_generate_circuit_regenerates_outdated_detector_database_at_custom_path(
    tmp_path: Path,
) -> None:
    stale_database_path = tmp_path / "database.pkl"
    stale_database = DetectorDatabase()
    stale_database.version = semver.Version(1, 0, 0)
    stale_database.to_file(stale_database_path)

    g = BlockGraph("Memory Experiment")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    compiled_graph = compile_block_graph(
        g,
        FIXED_BULK_CONVENTION,
        g.find_correlation_surfaces(),
        _DEFAULT_BLOCK_REPETITIONS,
    )

    with pytest.warns(TQECWarning, match="database will be regenerated"):
        compiled_graph.to_layer_tree().generate_circuit(1, database_path=stale_database_path)

    regenerated_database = DetectorDatabase.from_file(stale_database_path)
    assert regenerated_database.version == CURRENT_DATABASE_VERSION
