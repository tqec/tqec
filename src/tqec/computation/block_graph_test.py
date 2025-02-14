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
    v = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    assert g.num_cubes == 1
    assert g[v].kind == ZXCube.from_str("ZXZ")
    assert v in g

    with pytest.raises(TQECException, match="Cube already exists at position .*"):
        g.add_cube(Position3D(0, 0, 0), "XZX")

    v = g.add_cube(Position3D(1, 0, 0), "PORT", "P")
    assert g.num_cubes == 2
    assert g.num_ports == 1
    assert g[v].is_port

    with pytest.raises(TQECException, match=".* port with the same label .*"):
        g.add_cube(Position3D(10, 0, 0), "P", "P")


def test_block_graph_add_pipe() -> None:
    g = BlockGraph()
    with pytest.raises(TQECException, match="No cube at position .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(1, 0, 0),
        )
    u = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    v = g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_pipe(u, v)
    assert g.num_pipes == 1
    assert g.pipes[0].kind == PipeKind.from_str("ZXO")
    assert g.has_pipe_between(u, v)
    assert len(g.leaf_cubes) == 2
    assert g.get_degree(u) == 1
    assert len(g.pipes_at(u)) == 1

    with pytest.raises(TQECException, match=".* already a pipe between .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        )

    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    with pytest.raises(TQECException, match=r"No pipe between .*"):
        g.get_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))


def test_remove_block() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXZ")
    n3 = g.add_cube(Position3D(1, 0, 1), "P", "Out")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    assert g.num_cubes == 3
    assert g.num_pipes == 2
    assert g.num_ports == 2
    g.remove_cube(n1)
    assert g.num_cubes == 2
    assert g.num_pipes == 1
    assert g.num_ports == 1
    assert "In" not in g.ports

    g.remove_pipe(n2, n3)
    assert g.num_cubes == 2
    assert g.num_pipes == 0
    assert g.num_ports == 1
    assert not g.is_single_connected()


def test_block_graph_validate_y_cube() -> None:
    g = BlockGraph()
    u = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    v = g.add_cube(Position3D(1, 0, 0), "Y")
    g.add_pipe(u, v)
    with pytest.raises(TQECException, match="has non-timelike pipes connected"):
        g.validate()

    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 1), "Y")
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()
    n2 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n3 = g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()


def test_block_graph_validate_3d_corner() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "XZX")
    n3 = g.add_cube(Position3D(1, 0, 1), "Y")
    n4 = g.add_cube(Position3D(1, 1, 0), "P", "P")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    g.add_pipe(n2, n4, "XOZ")

    with pytest.raises(TQECException):
        g.validate()


def test_graph_shift() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    shifted = g.shift_by(dz=-1)
    assert shifted.num_cubes == 1
    assert shifted.cubes[0].position == Position3D(0, 0, 0)

    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, -1), ZXCube.from_str("ZXZ"))
    n2 = g.add_cube(Position3D(1, 0, -1), ZXCube.from_str("XZX"))
    n3 = g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    minz = min(cube.position.z for cube in g.cubes)
    shifted = g.shift_by(dz=-minz)
    assert shifted.num_cubes == 3
    assert shifted.num_pipes == 2
    assert {cube.position for cube in shifted.cubes} == {
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
        Position3D(0, 0, 1),
    }


def test_fill_ports() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "P", "in")
    g.add_cube(Position3D(1, 0, 0), "P", "out")
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0), "OZX")
    assert g.num_ports == 2
    assert g.num_cubes == 2

    g1 = g.clone()
    g1.fill_ports(ZXCube.from_str("XZX"))
    assert g1.num_ports == 0
    assert g1.num_cubes == 2

    g2 = g.clone()
    g2.fill_ports({"in": ZXCube.from_str("XZX")})
    assert g2.num_ports == 1
    assert g2.num_cubes == 2


def test_compose_graphs() -> None:
    g1 = BlockGraph("g1")
    n1 = g1.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g1.add_cube(Position3D(1, 0, 0), "P", "Out")
    g1.add_pipe(n1, n2, "OXZ")

    g2 = g1.clone()
    g2.name = "g2"
    g_composed = g1.compose(g2, "Out", "In")
    assert g_composed.name == "g1_composed_with_g2"
    assert g_composed.num_cubes == 3
    assert g_composed.num_ports == 2
    assert g_composed.ports == {"In": n1, "Out": Position3D(2, 0, 0)}
    assert g_composed[Position3D(1, 0, 0)].kind == ZXCube.from_str("ZXZ")


def test_single_connected() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    assert g.is_single_connected()

    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    assert not g.is_single_connected()

    g.add_pipe(n1, n2)
    assert g.is_single_connected()
