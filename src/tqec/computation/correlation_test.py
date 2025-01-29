import pytest

from tqec.computation.correlation import CorrelationSurface
from tqec.computation.zx_graph import ZXEdge, ZXGraph, ZXKind, ZXNode
from tqec.gallery.solo_node import solo_node_zx_graph
from tqec.utils.position import Position3D


def test_correlation_single_xz_node() -> None:
    g = solo_node_zx_graph("X")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    surface = correlation_surfaces[0]
    assert surface.has_single_node
    assert surface.external_stabilizer == {}
    assert surface.observables_at_nodes == {Position3D(0, 0, 0): ZXKind.Z}


@pytest.mark.parametrize("label_u", [None, "foo"])
@pytest.mark.parametrize("kind", [ZXKind.X, ZXKind.Z])
def test_correlation_two_xz_nodes(kind: ZXKind, label_u: str | None) -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), kind, label=label_u or ""),
        ZXNode(Position3D(0, 0, 1), kind),
    )
    assert g.find_correlation_surfaces() == [
        CorrelationSurface.from_span(
            g,
            frozenset(
                [
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), kind.with_zx_flipped()),
                        ZXNode(Position3D(0, 0, 1), kind.with_zx_flipped()),
                    )
                ]
            ),
        )
    ]


def test_correlation_two_xz_nodes_impossible() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.X),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    assert g.find_correlation_surfaces() == []


def test_correlation_hadamard() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.X),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        has_hadamard=True,
    )
    assert g.find_correlation_surfaces() == [
        CorrelationSurface.from_span(
            g,
            frozenset(
                [
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
                        ZXNode(Position3D(0, 0, 1), ZXKind.X),
                        has_hadamard=True,
                    )
                ]
            ),
        )
    ]


def test_correlation_y_node() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Y),
        ZXNode(Position3D(0, 0, 1), ZXKind.P, "out"),
    )
    correlation_surfaces = g.find_correlation_surfaces()
    assert correlation_surfaces == [
        CorrelationSurface.from_span(
            g,
            frozenset(
                [
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), ZXKind.X),
                        ZXNode(Position3D(0, 0, 1), ZXKind.X),
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
                        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
                    ),
                ]
            ),
        )
    ]
    assert correlation_surfaces[0].external_stabilizer == {"out": "Y"}


def test_correlation_port_passthrough() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, "in"),
        ZXNode(Position3D(1, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.Z),
        ZXNode(Position3D(2, 0, 0), ZXKind.P, "out"),
    )

    def _span(node_type: ZXKind) -> frozenset[ZXEdge]:
        return frozenset(
            [
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), node_type),
                    ZXNode(Position3D(1, 0, 0), node_type),
                ),
                ZXEdge(
                    ZXNode(Position3D(1, 0, 0), node_type),
                    ZXNode(Position3D(2, 0, 0), node_type),
                ),
            ]
        )

    x_span = _span(ZXKind.X)
    z_span = _span(ZXKind.Z)

    correlation_surfaces = g.find_correlation_surfaces()
    assert set(correlation_surfaces) == {
        CorrelationSurface.from_span(g, x_span),
        CorrelationSurface.from_span(g, z_span),
    }
    assert correlation_surfaces[0].external_stabilizer == {"in": "X", "out": "X"}
    assert correlation_surfaces[1].external_stabilizer == {"in": "Z", "out": "Z"}


def test_correlation_logical_s_via_gate_teleportation() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, "in"),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(0, 0, 2), ZXKind.P, "out"),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 0, 2), ZXKind.Y),
    )
    correlation_surfaces = g.find_correlation_surfaces()
    impl_external_stabilizers = [cs.external_stabilizer for cs in correlation_surfaces]
    assert all(
        [
            s in impl_external_stabilizers
            for s in [
                {"in": "Z", "out": "Z"},
                {"in": "X", "out": "Y"},
                {"in": "Y", "out": "X"},
            ]
        ]
    )


def test_correlation_four_node_circle() -> None:
    """Test against the following graph:
       o---o
       |   |
    ---o---o

    and

       o---o
       |   |
    ---o---o
       |
    """

    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(-1, 0, 0), ZXKind.P, "p1"),
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 1, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 0), ZXKind.Z),
        ZXNode(Position3D(0, 1, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 1, 0), ZXKind.Z),
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
    )

    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    assert correlation_surfaces[0].external_stabilizer == {"p1": "X"}

    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, -1, 0), ZXKind.P, "p2"),
    )
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 3
    assert correlation_surfaces[0].external_stabilizer == {"p1": "X", "p2": "X"}
    assert correlation_surfaces[1].external_stabilizer == {"p1": "Z", "p2": "Z"}
    assert correlation_surfaces[2].external_stabilizer == {"p1": "Z", "p2": "Z"}
