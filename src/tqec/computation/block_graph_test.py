import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, YCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Position3D


def test_block_graph_construction() -> None:
    g = BlockGraph("Test Block Graph")
    assert g.name == "Test Block Graph"
    assert len(g.nodes) == 0
    assert len(g.edges) == 0


def test_block_graph_add_cube() -> None:
    g = BlockGraph()
    g.add_node(Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")))
    assert g.num_nodes == 1
    assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("ZXZ")
    assert Position3D(0, 0, 0) in g

    with pytest.raises(TQECException, match="The graph already has a different node"):
        g.add_node(Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")))

    g.add_node(Cube(Position3D(1, 0, 0), Port(), label="test"))
    assert g.num_nodes == 2
    assert g.num_ports == 1
    assert g[Position3D(1, 0, 0)].is_port
    assert g.ports == {"test": Position3D(1, 0, 0)}

    with pytest.raises(
        TQECException,
        match="There is already a different port with label test in the graph",
    ):
        g.add_node(Cube(Position3D(2, 0, 0), Port(), label="test"))


def test_block_graph_add_pipe() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        PipeKind.from_str("OXZH"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 1), YCube()),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        PipeKind.from_str("XZO"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(2, 0, 0), Port(), label="out"),
    )
    assert g.num_nodes == 4
    assert g.num_edges == 3
    assert g.num_ports == 1
    assert g.ports == {"out": Position3D(2, 0, 0)}
    assert g.has_edge_between(Position3D(0, 0, 0), Position3D(1, 0, 0))
    assert g.get_edge(Position3D(0, 0, 0), Position3D(1, 0, 0)).kind.has_hadamard
    assert len(g.edges_at(Position3D(1, 0, 0))) == 3


def test_block_graph_validate_port() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), Port(), "test"),
        PipeKind.from_str("OXZ"),
    )
    g.add_edge(
        Cube(Position3D(2, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(1, 0, 0), Port(), "test"),
        PipeKind.from_str("OZX"),
    )
    with pytest.raises(TQECException, match="not have exactly one pipe connected."):
        g.validate()


def test_block_graph_validate_y_cube() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), YCube()),
        PipeKind.from_str("OXZ"),
    )
    with pytest.raises(TQECException, match="has non-timelike pipes connected"):
        g.validate()

    g = BlockGraph()
    g.add_node(Cube(Position3D(0, 0, 1), YCube()))
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()

    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 1), YCube()),
        PipeKind.from_str("ZXO"),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 2), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 1), YCube()),
        PipeKind.from_str("ZXO"),
    )
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()


def test_block_graph_validate_3d_corner() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        PipeKind.from_str("OXZH"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 1), YCube()),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        PipeKind.from_str("XZO"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(1, 1, 0), Port(), label="out"),
        PipeKind.from_str("XOZ"),
    )
    with pytest.raises(TQECException):
        g.validate()


def test_block_graph_validate_color_match() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XZX")),
        PipeKind.from_str("OXZ"),
    )
    with pytest.raises(TQECException):
        g.validate()


def test_shift_min_z_to_zero() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, -1), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, -1), ZXCube.from_str("XZX")),
        PipeKind.from_str("OXZH"),
    )
    g.add_edge(
        Cube(Position3D(0, 0, -1), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("ZXO"),
    )
    shifted = g.shift_min_z_to_zero()
    assert shifted.num_nodes == 3
    assert shifted.num_edges == 2
    assert {cube.position for cube in shifted.nodes} == {
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
        Position3D(0, 0, 1),
    }
