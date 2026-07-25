import os
import tempfile
from pathlib import Path

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import YHalfCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.three_cnots import three_cnots
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def rotated_cnot(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical CNOT gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If None, the four ports of the block graph will be left open.
            Otherwise, the ports will be filled with the cubes that have the
            initializations and measurements in the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical CNOT gate.

    """
    g = BlockGraph()

    nodes = [
        (Position3D(0, 0, 1), "P", "In_Control"),
        (Position3D(0, 1, 1), "ZXX", ""),
        (Position3D(0, 2, 1), "ZZX", ""),
        (Position3D(0, 3, 1), "P", "Out_Control"),
        (Position3D(0, 1, 0), "ZXX", ""),
        (Position3D(0, 2, 0), "ZZX", ""),
        (Position3D(1, 0, 0), "P", "In_Target"),
        (Position3D(1, 1, 0), "ZZX", ""),
        (Position3D(1, 2, 0), "ZZX", ""),
        (Position3D(1, 3, 0), "P", "Out_Target"),
    ]

    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5), (5, 8), (6, 7), (7, 8), (8, 9)]

    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if observable_basis == Basis.Z:
        g.fill_ports(ZXCube.from_str("ZZX"))
    elif observable_basis == Basis.X:
        g.fill_ports(ZXCube.from_str("ZXX"))
    return g


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


def test_rotated_cnot_collada_write_read() -> None:
    block_graph = rotated_cnot(Basis.Z)

    rotated_cnot_dae_path = Path(__file__).parent / "test_files/rotated_cnot.dae"
    block_graph_from_file = BlockGraph.from_dae_file(rotated_cnot_dae_path)

    assert block_graph_from_file == block_graph


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
                pop_faces_at_directions=("+X", "-Y"),
                show_correlation_surface=correlation_surface,
            )
            block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
            assert block_graph_from_file == block_graph

    os.remove(temp_file.name)


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
@pytest.mark.parametrize("y_is_init", [True, False], ids=["init", "meas"])
def test_y_cube_init_meas_roundtrip(pipe_length: float, y_is_init: bool) -> None:
    """Y init (pipe above, +0.5 shift) and Y meas (pipe below, -0.5 shift) survive roundtrip."""
    g = BlockGraph()
    if y_is_init:
        g.add_cube(Position3D(0, 0, 0), "Y")
        g.add_cube(Position3D(0, 0, 1), "ZXX")
        g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    else:
        g.add_cube(Position3D(0, 0, 0), "ZXX")
        g.add_cube(Position3D(0, 0, 1), "Y")
        g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name, pipe_length)
        g2 = BlockGraph.from_dae_file(f.name)
    os.remove(f.name)
    assert g2 == g


def test_dae_roundtrip_preserves_y_cube_position_above_origin():
    """Y half cubes at z > 0 must survive a write -> read round-trip.

    Before this fix, offset_y_cube_position(pos, pipe_length) divided z by
    (1 + pipe_length) and int_position_before_scale(..., pipe_length) did so
    again, scaling Y cube z down by an extra factor of (1 + pipe_length).
    A Y at TQEC (1,1,3) landed at (1,1,1), colliding with any cube there.
    """
    g = BlockGraph()
    g.add_cube(Position3D(1, 1, 1), ZXCube.from_str("XZZ"))
    g.add_cube(Position3D(1, 1, 2), ZXCube.from_str("XZZ"))
    g.add_cube(Position3D(1, 1, 3), YHalfCube())
    g.add_pipe(Position3D(1, 1, 1), Position3D(1, 1, 2), PipeKind.from_str("XZO"))
    g.add_pipe(Position3D(1, 1, 2), Position3D(1, 1, 3), PipeKind.from_str("XZO"))

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        g2 = BlockGraph.from_dae_file(f.name)

    y_cubes = [c for c in g2.cubes if isinstance(c.kind, YHalfCube)]
    assert len(y_cubes) == 1
    assert y_cubes[0].position == Position3D(1, 1, 3)
