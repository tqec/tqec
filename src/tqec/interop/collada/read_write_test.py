import os
import tempfile

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.gallery.cnot import cnot, rotated_cnot
from tqec.gallery.three_cnots import three_cnots
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_logical_cnot_collada_write_read(pipe_length: float) -> None:
    block_graph = cnot(Basis.X)

    # Set `delete=False` to be compatible with Windows
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph

    # Manually delete the temporary file
    os.remove(temp_file.name)


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_rotated_cnot_collada_write_read(pipe_length: float) -> None:
    block_graph = rotated_cnot(Basis.X)
    cubes_in_blockgraph = [cube for cube in block_graph.cubes]
    pipes_in_blockgraph = [
        (pipe.u.position, pipe.v.position, pipe.kind) for pipe in block_graph.pipes
    ]

    block_graph_from_file = BlockGraph.from_dae_file("./assets/rotations_cnot.dae")
    cubes_from_dae = [cube for cube in block_graph_from_file.cubes]
    pipes_from_dae = [
        (pipe.u.position, pipe.v.position, pipe.kind)
        for pipe in block_graph_from_file.pipes
    ]

    match_cubes = [(cube in cubes_in_blockgraph) for cube in cubes_from_dae]
    match_pipes = [(pipe in pipes_in_blockgraph) for pipe in pipes_from_dae]

    assert all([match_cubes, match_pipes])


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_three_cnots_collada_write_read(pipe_length: float) -> None:
    block_graph = three_cnots(Basis.Z)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph
    os.remove(temp_file.name)


def test_open_ports_roundtrip_not_equal() -> None:
    block_graph = cnot()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, 2.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file != block_graph
    os.remove(temp_file.name)


def test_y_cube_positioning_during_roundtrip() -> None:
    g = BlockGraph()
    u = g.add_cube(Position3D(0, 0, 0), "Y")
    v = g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(u, v)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        g.to_dae_file(temp_file.name, 10.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == g
    os.remove(temp_file.name)


def test_collada_write_read_with_correlation_surface() -> None:
    block_graph = cnot(Basis.X)
    correlation_surfaces = block_graph.find_correlation_surfaces()

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        for correlation_surface in correlation_surfaces:
            block_graph.to_dae_file(
                temp_file.name,
                2.0,
                pop_faces_at_direction="+X",
                show_correlation_surface=correlation_surface,
            )
            block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
            assert block_graph_from_file == block_graph

    os.remove(temp_file.name)
