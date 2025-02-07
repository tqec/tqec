import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Position3D


def test_block_graph_construction() -> None:
    g = BlockGraph()
    assert len(g.cubes) == 0
    assert len(g.pipes) == 0


def test_block_graph_add_cube() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    assert g.num_cubes == 1
    assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("ZXZ")
    assert Position3D(0, 0, 0) in g

    with pytest.raises(TQECException, match="Cube already exists at position .*"):
        g.add_cube(Position3D(0, 0, 0), "XZX")

    g.add_cube(Position3D(1, 0, 0), "PORT", "P")
    assert g.num_cubes == 2
    assert g.num_ports == 1
    assert g[Position3D(1, 0, 0)].is_port

    with pytest.raises(TQECException, match=".* port with the same label .*"):
        g.add_cube(Position3D(10, 0, 0), "P", "P")


def test_block_graph_add_pipe() -> None:
    g = BlockGraph()
    with pytest.raises(TQECException, match="No cube at position .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(1, 0, 0),
        )
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_pipe(
        Position3D(0, 0, 0),
        Position3D(0, 0, 1),
    )
    assert g.num_pipes == 1
    assert g.pipes[0].kind == PipeKind.from_str("ZXO")
    assert g.has_pipe_between(Position3D(0, 0, 0), Position3D(0, 0, 1))
    assert len(g.leaf_cubes) == 2
    assert g.get_degree(Position3D(0, 0, 0)) == 1
    assert len(g.pipes_at(Position3D(0, 0, 0))) == 1

    with pytest.raises(TQECException, match=".* already a pipe between .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        )

    with pytest.raises(TQECException, match=r"No pipe between .*"):
        g.get_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))


def test_block_graph_validate_y_cube() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "Y")
    g.add_pipe(
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
    )
    with pytest.raises(TQECException, match="has non-timelike pipes connected"):
        g.validate()

    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), "Y")
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()


def test_block_graph_validate_3d_corner() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "XZX")
    g.add_cube(Position3D(1, 0, 1), "Y")
    g.add_cube(Position3D(1, 1, 0), "P", "P")
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 0))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 1, 0), "XOZ")

    with pytest.raises(TQECException):
        g.validate()


def test_graph_shift() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, -1), ZXCube.from_str("ZXZ"))
    g.add_cube(Position3D(1, 0, -1), ZXCube.from_str("XZX"))
    g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_pipe(Position3D(0, 0, -1), Position3D(1, 0, -1))
    g.add_pipe(Position3D(0, 0, -1), Position3D(0, 0, 0))
    minz = min(cube.position.z for cube in g.cubes)
    shifted = g.shift_by(dz=-minz)
    assert shifted.num_cubes == 3
    assert shifted.num_pipes == 2
    assert {cube.position for cube in shifted.cubes} == {
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
        Position3D(0, 0, 1),
    }
