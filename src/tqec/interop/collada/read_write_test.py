import os
import tempfile

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode
from tqec.gallery.logical_cnot import logical_cnot_block_graph, logical_cnot_zx_graph
from tqec.gallery.three_cnots import three_cnots_block_graph, three_cnots_zx_graph
from tqec.position import Direction3D, Position3D, SignedDirection3D


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_logical_cnot_collada_write_read(pipe_length: float) -> None:
    block_graph = logical_cnot_block_graph("X")

    # Set `delete=False` to be compatible with Windows
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph
        assert block_graph_from_file.to_zx_graph() == logical_cnot_zx_graph("Z")

    # Manually delete the temporary file
    os.remove(temp_file.name)


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_three_cnots_collada_write_read(pipe_length: float) -> None:
    block_graph = three_cnots_block_graph("Z")
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph
        assert block_graph_from_file.to_zx_graph() == three_cnots_zx_graph("X")
    os.remove(temp_file.name)


def test_open_ports_roundtrip_not_equal() -> None:
    block_graph = logical_cnot_block_graph("BOTH")
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, 2.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file != block_graph
    os.remove(temp_file.name)


def test_y_cube_positioning_during_roundtrip() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Y),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    block_graph = g.to_block_graph()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, 10.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph
        assert block_graph_from_file.to_zx_graph() == g
    os.remove(temp_file.name)


def test_collada_write_read_with_correlation_surface() -> None:
    block_graph = logical_cnot_block_graph("X")
    correlation_surfaces = block_graph.to_zx_graph().find_correration_surfaces()

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        for correlation_surface in correlation_surfaces:
            block_graph.to_dae_file(
                temp_file.name,
                2.0,
                pop_faces_at_direction=SignedDirection3D(Direction3D.X, True),
                show_correlation_surface=correlation_surface,
            )
            block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
            assert block_graph_from_file == block_graph
            assert block_graph_from_file.to_zx_graph() == logical_cnot_zx_graph("Z")

    os.remove(temp_file.name)
