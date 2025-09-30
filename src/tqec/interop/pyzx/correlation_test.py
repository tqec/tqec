from fractions import Fraction

import pytest
from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.correlation import (
    find_correlation_surfaces,
)
from tqec.utils.enums import Basis


def test_correlation_single_xz_node() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    surfaces = find_correlation_surfaces(g)
    assert len(surfaces) == 1
    surface = surfaces[0]
    assert surface.is_single_node
    assert next(iter(surface.span)) == ZXEdge(ZXNode(0, Basis.Z), ZXNode(0, Basis.Z))


@pytest.mark.parametrize("ty", [VertexType.X, VertexType.Z])
def test_correlation_two_xz_nodes(ty: VertexType) -> None:
    g = GraphS()
    g.add_vertex(ty)
    g.add_vertex(ty)
    g.add_edge((0, 1))
    surfaces = find_correlation_surfaces(g)
    assert len(surfaces) == 1
    b = Basis.Z if ty == VertexType.X else Basis.X
    assert surfaces[0].span == frozenset([ZXEdge(ZXNode(0, b), ZXNode(1, b))])


def test_correlation_two_xz_nodes_impossible() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    g.add_vertex(VertexType.Z)
    g.add_edge((0, 1))
    assert find_correlation_surfaces(g) == []


def test_correlation_hadamard() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    g.add_vertex(VertexType.Z)
    g.add_edge((0, 1), EdgeType.HADAMARD)
    surfaces = find_correlation_surfaces(g)
    assert len(surfaces) == 1
    assert surfaces[0].span == frozenset(
        [
            ZXEdge(
                ZXNode(0, Basis.Z),
                ZXNode(1, Basis.X),
            )
        ]
    )


def test_correlation_y_node() -> None:
    g = GraphS()
    g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    g.add_vertex()
    g.add_edge((0, 1))
    surfaces = find_correlation_surfaces(g)
    assert len(surfaces) == 1
    assert surfaces[0].span == frozenset(
        [
            ZXEdge(
                ZXNode(0, Basis.X),
                ZXNode(1, Basis.X),
            ),
            ZXEdge(
                ZXNode(0, Basis.Z),
                ZXNode(1, Basis.Z),
            ),
        ]
    )


def test_correlation_port_passthrough() -> None:
    g = GraphS()
    g.add_vertices(3)
    g.add_edges([(0, 1), (1, 2)])
    g.set_type(1, VertexType.X)

    surfaces = find_correlation_surfaces(g)
    assert surfaces == [
        CorrelationSurface(
            frozenset(
                [
                    ZXEdge(ZXNode(0, Basis.X), ZXNode(1, Basis.X)),
                    ZXEdge(ZXNode(1, Basis.X), ZXNode(2, Basis.X)),
                ]
            )
        ),
        CorrelationSurface(
            frozenset(
                [
                    ZXEdge(ZXNode(0, Basis.Z), ZXNode(1, Basis.Z)),
                    ZXEdge(ZXNode(1, Basis.Z), ZXNode(2, Basis.Z)),
                ]
            )
        ),
    ]


def test_correlation_logical_s_via_gate_teleportation() -> None:
    g = GraphS()
    g.add_vertex()
    g.add_vertex(VertexType.Z)
    g.add_vertex()
    g.add_vertex(VertexType.Z)
    g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    g.add_edges([(0, 1), (1, 2), (1, 3), (3, 4)])
    surfaces = set(find_correlation_surfaces(g, reduce_to_minimal_generators=False))
    assert len(surfaces) == 3
    assert {
        CorrelationSurface(
            frozenset(
                {
                    ZXEdge(ZXNode(0, Basis.X), ZXNode(1, Basis.X)),
                    ZXEdge(ZXNode(0, Basis.Z), ZXNode(1, Basis.Z)),
                    ZXEdge(ZXNode(1, Basis.X), ZXNode(2, Basis.X)),
                    ZXEdge(ZXNode(1, Basis.X), ZXNode(3, Basis.X)),
                    ZXEdge(ZXNode(1, Basis.Z), ZXNode(3, Basis.Z)),
                    ZXEdge(ZXNode(3, Basis.X), ZXNode(4, Basis.X)),
                    ZXEdge(ZXNode(3, Basis.Z), ZXNode(4, Basis.Z)),
                }
            )
        ),
        CorrelationSurface(
            frozenset(
                {
                    ZXEdge(ZXNode(1, Basis.Z), ZXNode(2, Basis.Z)),
                    ZXEdge(ZXNode(0, Basis.Z), ZXNode(1, Basis.Z)),
                }
            )
        ),
    }.issubset(surfaces)

    generators = set(find_correlation_surfaces(g))
    assert len(generators) == 2
    assert {s.external_stabilizer([0, 2]) for s in generators} == {"ZZ", "XY"}


def test_correlation_four_node_circle() -> None:
    """Test against the below graphs.

       o---o
       |   |
    ---o---o

    and

       o---o
       |   |
    ---o---o
       |
    """
    g = GraphS()
    g.add_vertices(5)
    for i in range(1, 5):
        g.set_type(i, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (2, 3), (3, 4), (1, 4)])

    surfaces = find_correlation_surfaces(g)
    assert len(surfaces) == 1
    surface = surfaces[0]
    pauli_web = surface.to_pauli_web(g)
    assert CorrelationSurface.from_pauli_web(pauli_web) == surface

    g.add_vertex()
    g.add_edge((1, 5))
    assert len(find_correlation_surfaces(g, reduce_to_minimal_generators=False)) == 3
