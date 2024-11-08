import pytest

from tqec.exceptions import TQECException
from tqec.position import Direction3D, Position3D
from tqec.computation.zx_graph import ZXKind, ZXEdge, ZXGraph, ZXNode


def test_zx_node() -> None:
    node = ZXNode(Position3D(0, 0, 0), ZXKind.Z)
    assert node.is_zx_node
    assert not node.is_port
    assert str(node) == "Z(0,0,0)"

    node = ZXNode(Position3D(0, 1, 4), ZXKind.P, label="test")
    assert node.is_port
    assert str(node) == "PORT(0,1,4)"

    with pytest.raises(TQECException, match="A port node must have a non-empty label."):
        ZXNode(Position3D(0, 0, 0), ZXKind.P)

    node = ZXNode(Position3D(1, 0, 0), ZXKind.Y)
    assert node.is_y_node
    assert str(node) == "Y(1,0,0)"


def test_zx_edge() -> None:
    with pytest.raises(TQECException, match="An edge must connect two nearby nodes."):
        ZXEdge(
            ZXNode(Position3D(0, 0, 0), ZXKind.Z),
            ZXNode(Position3D(2, 0, 0), ZXKind.Z),
        )

    edge = ZXEdge(
        ZXNode(Position3D(2, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    assert edge.u.position == Position3D(1, 0, 0)
    assert edge.v.position == Position3D(2, 0, 0)
    assert edge.direction == Direction3D.X
    assert str(edge) == "X(1,0,0)-Z(2,0,0)"

    edge = ZXEdge(
        ZXNode(Position3D(2, 1, 0), ZXKind.Y),
        ZXNode(Position3D(2, 0, 0), ZXKind.X),
        has_hadamard=True,
    )
    assert edge.has_hadamard
    assert str(edge) == "X(2,0,0)-H-Y(2,1,0)"
    assert edge.direction == Direction3D.Y


def test_zx_graph_construction() -> None:
    g = ZXGraph("Test ZX Graph")
    assert g.name == "Test ZX Graph"
    assert len(g.nodes) == 0
    assert len(g.edges) == 0


def test_zx_graph_add_node() -> None:
    g = ZXGraph()
    g.add_node(ZXNode(Position3D(0, 0, 0), ZXKind.Z))
    assert g.num_nodes == 1
    assert g[Position3D(0, 0, 0)].kind == ZXKind.Z
    assert Position3D(0, 0, 0) in g

    with pytest.raises(TQECException, match="The graph already has a different node"):
        g.add_node(ZXNode(Position3D(0, 0, 0), ZXKind.X))

    g.add_node(ZXNode(Position3D(1, 0, 0), ZXKind.P, label="test"))
    assert g.num_nodes == 2
    assert g.num_ports == 1
    assert g[Position3D(1, 0, 0)].kind == ZXKind.P
    assert g.ports == {"test": Position3D(1, 0, 0)}

    with pytest.raises(
        TQECException,
        match="There is already a different port with label test in the graph",
    ):
        g.add_node(ZXNode(Position3D(2, 0, 0), ZXKind.P, label="test"))


def test_zx_graph_add_edge() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
        has_hadamard=True,
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Y),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
        ZXNode(Position3D(2, 0, 0), ZXKind.P, label="out"),
    )
    assert g.num_nodes == 4
    assert g.num_edges == 3
    assert g.num_ports == 1
    assert g.ports == {"out": Position3D(2, 0, 0)}
    assert g.has_edge_between(Position3D(0, 0, 0), Position3D(1, 0, 0))
    assert g.get_edge(Position3D(0, 0, 0), Position3D(1, 0, 0)).has_hadamard


def test_zx_graph_edges_at() -> None:
    g = ZXGraph()
    for i, pos in enumerate(
        [
            Position3D(1, 0, 0),
            Position3D(0, 1, 0),
            Position3D(-1, 0, 0),
            Position3D(0, -1, 0),
        ]
    ):
        g.add_edge(
            ZXNode(Position3D(0, 0, 0), ZXKind.Z),
            ZXNode(pos, ZXKind.P, f"p{i}"),
        )
    assert len(g.edges_at(Position3D(0, 0, 0))) == 4
    assert len(g.edges_at(Position3D(1, 0, 0))) == 1


def test_zx_graph_fill_ports() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, label="in"),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
        ZXNode(Position3D(2, 0, 0), ZXKind.P, label="out"),
    )
    assert g.num_nodes == 3
    assert g.num_ports == 2
    with pytest.raises(TQECException, match="There is no port with label unknown"):
        g.fill_ports({"unknown": ZXKind.Z})

    with pytest.raises(TQECException, match="Cannot fill the ports with port kind"):
        g.fill_ports({"in": ZXKind.P})

    g.fill_ports(ZXKind.X)
    assert g.num_ports == 0
    assert g[Position3D(0, 0, 0)].kind == ZXKind.X
    assert g[Position3D(2, 0, 0)].kind == ZXKind.X
    new_edge = g.get_edge(Position3D(0, 0, 0), Position3D(1, 0, 0))
    assert new_edge.u == ZXNode(Position3D(0, 0, 0), ZXKind.X)
    assert new_edge.v == ZXNode(Position3D(1, 0, 0), ZXKind.X)
    assert g.num_nodes == 3
    assert g.num_ports == 0


def test_zx_graph_with_zx_flipped() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, label="p1"),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
        ZXNode(Position3D(2, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(2, 0, 0), ZXKind.Z),
        ZXNode(Position3D(2, 0, -1), ZXKind.Y),
    )
    g.add_edge(
        ZXNode(Position3D(2, 0, 0), ZXKind.Z),
        ZXNode(Position3D(2, 0, 1), ZXKind.P, label="p2"),
    )
    assert g.num_nodes == 5
    assert g.num_ports == 2
    assert g.num_edges == 4


def test_zx_graph_check_invariants() -> None:
    g = ZXGraph()
    g.add_node(ZXNode(Position3D(0, 0, 0), ZXKind.Z))
    g.add_node(ZXNode(Position3D(1, 0, 0), ZXKind.X))
    with pytest.raises(
        TQECException,
        match="The ZX graph must be a single connected component",
    ):
        g.check_invariants()

    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.P, "test"),
    )
    g.add_edge(
        ZXNode(Position3D(2, 0, 0), ZXKind.X),
        ZXNode(Position3D(1, 0, 0), ZXKind.P, "test"),
    )
    with pytest.raises(TQECException, match="The port/Y node must be a leaf node."):
        g.check_invariants()
