from collections.abc import Callable, Sequence
from fractions import Fraction
from itertools import product

import pytest
from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.compile.observables.abstract_observable import _check_correlation_surface_validity
from tqec.computation import block_graph as block_graph_module
from tqec.computation._correlation import _find_correlation_surface_containing
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import (
    CorrelationSurface,
    ZXEdge,
    ZXNode,
    find_correlation_surface_containing,
    find_correlation_surfaces,
)
from tqec.gallery import memory
from tqec.gallery.cnot import cnot
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.steane_encoding import steane_encoding
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def test_zx_node() -> None:
    n1 = ZXNode(Position3D(0, 0, 0), Basis.Z)
    n2 = ZXNode(Position3D(1, 0, 0), Basis.X)
    assert n1 < n2


def test_zx_edge() -> None:
    e1 = ZXEdge.sorted(
        ZXNode(Position3D(1, 0, 0), Basis.Z),
        ZXNode(Position3D(0, 0, 0), Basis.Z),
    )
    assert e1.u < e1.v
    assert not e1.is_self_loop
    assert not e1.has_hadamard

    e2 = ZXEdge(
        ZXNode(Position3D(1, 0, 0), Basis.Z),
        ZXNode(Position3D(2, 0, 0), Basis.X),
    )
    assert e2.has_hadamard

    e3 = ZXEdge(
        ZXNode(Position3D(0, 0, 0), Basis.Z),
        ZXNode(Position3D(0, 0, 0), Basis.Z),
    )
    assert e3.is_self_loop


def test_single_node_correlation_surface() -> None:
    surface = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.Z),
                    ZXNode(Position3D(0, 0, 0), Basis.Z),
                ),
            ]
        )
    )
    assert surface.bases_at(Position3D(0, 0, 0)) == {Basis.Z}
    assert surface.is_single_node
    assert surface.positions == {Position3D(0, 0, 0)}
    assert surface.external_stabilizer([Position3D(0, 0, 0)]) == "Z"
    assert surface.area == 1


def test_y_edge_correlation_surface() -> None:
    surface = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.Z),
                    ZXNode(Position3D(1, 0, 0), Basis.Z),
                ),
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.X),
                    ZXNode(Position3D(1, 0, 0), Basis.X),
                ),
            ]
        )
    )
    assert surface.bases_at(Position3D(0, 0, 0)) == {Basis.Z, Basis.X}
    assert surface.bases_at(Position3D(1, 0, 0)) == {Basis.Z, Basis.X}
    assert not surface.is_single_node
    assert surface.positions == {Position3D(0, 0, 0), Position3D(1, 0, 0)}
    assert surface.external_stabilizer([Position3D(0, 0, 0), Position3D(1, 0, 0)]) == "YY"
    assert surface.area == 4


def test_correlation_surface_xor() -> None:
    s1 = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.Z),
                    ZXNode(Position3D(1, 0, 0), Basis.Z),
                ),
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.X),
                    ZXNode(Position3D(1, 0, 0), Basis.X),
                ),
            ]
        )
    )
    s2 = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(Position3D(0, 0, 0), Basis.X),
                    ZXNode(Position3D(1, 0, 0), Basis.X),
                ),
            ]
        )
    )
    s12 = s1 ^ s2
    assert s12.span == frozenset(
        [
            ZXEdge(
                ZXNode(Position3D(0, 0, 0), Basis.Z),
                ZXNode(Position3D(1, 0, 0), Basis.Z),
            ),
        ]
    )


def test_correlation_single_xz_node() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    pg = PositionedZX(g, {0: Position3D(0, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    assert len(surfaces) == 1
    surface = surfaces[0]
    assert surface.is_single_node
    assert next(iter(surface.span)) == ZXEdge(
        ZXNode(Position3D(0, 0, 0), Basis.Z), ZXNode(Position3D(0, 0, 0), Basis.Z)
    )


@pytest.mark.parametrize("ty", [VertexType.X, VertexType.Z])
def test_correlation_two_xz_nodes(ty: VertexType) -> None:
    g = GraphS()
    g.add_vertex(ty)
    g.add_vertex(ty)
    g.add_edge((0, 1))
    pg = PositionedZX(g, {0: Position3D(0, 0, 0), 1: Position3D(1, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    assert len(surfaces) == 1
    b = Basis.Z if ty == VertexType.X else Basis.X
    assert surfaces[0].span == frozenset(
        [ZXEdge(ZXNode(Position3D(0, 0, 0), b), ZXNode(Position3D(1, 0, 0), b))]
    )


def test_correlation_two_xz_nodes_impossible() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    g.add_vertex(VertexType.Z)
    g.add_edge((0, 1))
    pg = PositionedZX(g, {0: Position3D(0, 0, 0), 1: Position3D(1, 0, 0)})
    assert find_correlation_surfaces(pg) == []


def test_correlation_hadamard() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    g.add_vertex(VertexType.Z)
    g.add_edge((0, 1), EdgeType.HADAMARD)
    pg = PositionedZX(g, {0: Position3D(0, 0, 0), 1: Position3D(1, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    assert len(surfaces) == 1
    assert surfaces[0].span == frozenset(
        [
            ZXEdge(
                ZXNode(Position3D(0, 0, 0), Basis.Z),
                ZXNode(Position3D(1, 0, 0), Basis.X),
            )
        ]
    )


def test_correlation_y_node() -> None:
    g = GraphS()
    g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    g.add_vertex()
    g.add_edge((0, 1))
    pg = PositionedZX(g, {0: Position3D(0, 0, 0), 1: Position3D(0, 0, 1)})
    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    assert len(surfaces) == 1
    assert surfaces[0].span == frozenset(
        [
            ZXEdge(
                ZXNode(Position3D(0, 0, 0), Basis.X),
                ZXNode(Position3D(0, 0, 1), Basis.X),
            ),
            ZXEdge(
                ZXNode(Position3D(0, 0, 0), Basis.Z),
                ZXNode(Position3D(0, 0, 1), Basis.Z),
            ),
        ]
    )


def test_correlation_port_passthrough() -> None:
    g = GraphS()
    g.add_vertices(3)
    g.add_edges([(0, 1), (1, 2)])
    g.set_type(1, VertexType.X)
    pg = PositionedZX(g, {0: Position3D(0, 0, 0), 1: Position3D(0, 0, 1), 2: Position3D(0, 0, 2)})

    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    assert surfaces == [
        CorrelationSurface(
            frozenset(
                [
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), Basis.X), ZXNode(Position3D(0, 0, 1), Basis.X)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.X), ZXNode(Position3D(0, 0, 2), Basis.X)
                    ),
                ]
            )
        ),
        CorrelationSurface(
            frozenset(
                [
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), Basis.Z), ZXNode(Position3D(0, 0, 1), Basis.Z)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.Z), ZXNode(Position3D(0, 0, 2), Basis.Z)
                    ),
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
    pg = PositionedZX(
        g,
        {
            0: Position3D(0, 0, 0),
            1: Position3D(0, 0, 1),
            2: Position3D(0, 0, 2),
            3: Position3D(1, 0, 1),
            4: Position3D(1, 0, 0),
        },
    )
    surfaces = set(find_correlation_surfaces(pg))
    assert len(surfaces) == 2
    assert {
        CorrelationSurface(
            frozenset(
                {
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), Basis.X), ZXNode(Position3D(0, 0, 1), Basis.X)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), Basis.Z), ZXNode(Position3D(0, 0, 1), Basis.Z)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.X), ZXNode(Position3D(0, 0, 2), Basis.X)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.X), ZXNode(Position3D(1, 0, 1), Basis.X)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.Z), ZXNode(Position3D(1, 0, 1), Basis.Z)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(1, 0, 0), Basis.X), ZXNode(Position3D(1, 0, 1), Basis.X)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(1, 0, 0), Basis.Z), ZXNode(Position3D(1, 0, 1), Basis.Z)
                    ),
                }
            )
        ),
        CorrelationSurface(
            frozenset(
                {
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 1), Basis.Z), ZXNode(Position3D(0, 0, 2), Basis.Z)
                    ),
                    ZXEdge(
                        ZXNode(Position3D(0, 0, 0), Basis.Z), ZXNode(Position3D(0, 0, 1), Basis.Z)
                    ),
                }
            )
        ),
    } == set(surfaces)


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
    position_mapping = {
        0: Position3D(0, 0, 0),
        1: Position3D(1, 0, 0),
        2: Position3D(2, 0, 0),
        3: Position3D(2, 0, 1),
        4: Position3D(1, 0, 1),
    }
    pg = PositionedZX(g, position_mapping)

    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    assert len(surfaces) == 1
    g.add_vertex()
    g.add_edge((1, 5))
    position_mapping[5] = Position3D(1, 0, -1)
    pg = PositionedZX(g, position_mapping)
    assert len(find_correlation_surfaces(pg)) == 2


@pytest.mark.parametrize(
    ["bg", "basis"], tuple(product([memory, steane_encoding], [Basis.X, Basis.Z]))
)
def test_correlation_representations_conversion(
    bg: Callable[[Basis], BlockGraph], basis: Basis
) -> None:
    pg = bg(basis).to_zx_graph()
    for surface in find_correlation_surfaces(pg):
        assert (
            surface._to_mutable_graph_representation(pg).to_immutable_public_representation(pg)
            == surface
        )


def _positioned(g: GraphS, positions: dict[int, tuple[int, int, int]]) -> PositionedZX:
    """Wrap an abstract ZX graph in a ``PositionedZX`` with a hand-picked valid embedding."""
    return PositionedZX(g, {v: Position3D(*xyz) for v, xyz in positions.items()})


def test_correlation_disconnected_components_are_summed() -> None:
    # two disjoint Z-Z pairs
    g = GraphS()
    g.add_vertices(4)
    for v in range(4):
        g.set_type(v, VertexType.Z)
    g.add_edges([(0, 1), (2, 3)])
    pg = _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (0, 1, 0), 3: (1, 1, 0)})
    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, pg)
    # one generator per component, each only spanning its own component: the products of
    # generators from different components are not enumerated
    assert surfaces == [
        CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[1], Basis.X))])),
        CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[2], Basis.X), ZXNode(pg[3], Basis.X))])),
    ]


def _signature_span(
    surfaces: Sequence[CorrelationSurface], leaves: Sequence[Position3D]
) -> frozenset[int]:
    """Compute a canonical form of the GF(2) span of the surfaces' signatures at the leaves."""
    pauli_bits = {"I": 0, "X": 1, "Z": 2, "Y": 3}
    pivots: dict[int, int] = {}
    for surface in surfaces:
        signature = 0
        for i, pauli in enumerate(surface.external_stabilizer(list(leaves))):
            signature |= pauli_bits[pauli] << (2 * i)
        while signature:
            highest_bit = signature.bit_length() - 1
            if highest_bit in pivots:
                signature ^= pivots[highest_bit]
            else:
                pivots[highest_bit] = signature
                break
    for highest_bit in sorted(pivots, reverse=True):
        pivot = pivots[highest_bit]
        for other, vector in pivots.items():
            if other != highest_bit and (vector >> highest_bit) & 1:
                pivots[other] = vector ^ pivot
    return frozenset(pivots.values())


def _assert_vertex_ordering_matches_default(
    pg: PositionedZX, orderings: list[list[set[int]]]
) -> None:
    """Check the ordering-based search is equivalent to the default one.

    Both must return the same number of generators, independent at the leaves, and spanning the
    same correlations between the open leaves. The signatures at the closed leaves may differ:
    the generators are only unique up to correlation surfaces invisible at the open leaves.
    """
    g = pg.g
    leaf_vertices = sorted(v for v in g.vertices() if g.vertex_degree(v) == 1)
    leaves = [pg[v] for v in leaf_vertices]
    open_leaves = [pg[v] for v in leaf_vertices if g.type(v) is VertexType.BOUNDARY]
    default = find_correlation_surfaces(pg)
    for ordering in orderings:
        surfaces = find_correlation_surfaces(pg, vertex_ordering=ordering)
        for surface in surfaces:
            _check_correlation_surface_validity(surface, pg)
        assert len(surfaces) == len(default)
        assert len(_signature_span(surfaces, leaves)) == len(surfaces)
        assert _signature_span(surfaces, open_leaves) == _signature_span(default, open_leaves)


def _hadamard_chain_graph() -> PositionedZX:
    # port - X - H - Z - port
    g = GraphS()
    g.add_vertices(4)
    g.set_type(1, VertexType.X)
    g.set_type(2, VertexType.Z)
    g.add_edge((0, 1))
    g.add_edge((1, 2), EdgeType.HADAMARD)
    g.add_edge((2, 3))
    return _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (2, 0, 0), 3: (3, 0, 0)})


def _disconnected_graph_with_impossible_component() -> PositionedZX:
    # an X-Z pair supporting no correlation surface + a Z-Z pair
    g = GraphS()
    g.add_vertices(4)
    g.set_type(0, VertexType.X)
    for v in range(1, 4):
        g.set_type(v, VertexType.Z)
    g.add_edges([(0, 1), (2, 3)])
    return _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (0, 1, 0), 3: (1, 1, 0)})


def _circle_with_leaf_graph() -> PositionedZX:
    g = GraphS()
    g.add_vertices(6)
    for i in range(1, 5):
        g.set_type(i, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (2, 3), (3, 4), (1, 4), (1, 5)])
    # 1 is a hub; the 1-2-3-4 cycle is a unit square, with leaves 0 and 5 on either side of 1
    return _positioned(
        g,
        {0: (-1, 0, 0), 1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0), 5: (0, -1, 0)},
    )


def _hadamard_cycle_graph() -> PositionedZX:
    # a cycle crossing any two-part cut twice, with two hadamard edges
    g = GraphS()
    g.add_vertices(6)
    g.set_type(1, VertexType.Z)
    g.set_type(2, VertexType.Z)
    g.set_type(3, VertexType.X)
    g.set_type(4, VertexType.X)
    g.add_edge((0, 1))
    g.add_edge((1, 2))
    g.add_edge((1, 3), EdgeType.HADAMARD)
    g.add_edge((2, 4), EdgeType.HADAMARD)
    g.add_edge((3, 4))
    g.add_edge((4, 5))
    # the 1-2-4-3 cycle is a unit square, with leaves 0 and 5 dangling off vertices 1 and 4
    return _positioned(
        g,
        {0: (-1, 0, 0), 1: (0, 0, 0), 2: (0, 1, 0), 3: (1, 0, 0), 4: (1, 1, 0), 5: (2, 1, 0)},
    )


def _s_gate_teleportation_graph() -> PositionedZX:
    g = GraphS()
    g.add_vertex()
    g.add_vertex(VertexType.Z)
    g.add_vertex()
    g.add_vertex(VertexType.Z)
    g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    g.add_edges([(0, 1), (1, 2), (1, 3), (3, 4)])
    # the Z(1/2) spider 4 dangles off vertex 3 in the time direction
    return _positioned(g, {0: (-1, 0, 0), 1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0), 4: (0, 1, 1)})


def _hub_with_ports_and_closed_leaves_graph() -> PositionedZX:
    # an X hub with two ports and two closed Z leaves: correlation surfaces invisible at the
    # ports exist and must not be part of the generators
    g = GraphS()
    g.add_vertices(5)
    g.set_type(2, VertexType.X)
    g.set_type(3, VertexType.Z)
    g.set_type(4, VertexType.Z)
    g.add_edges([(0, 2), (1, 2), (2, 3), (2, 4)])
    return _positioned(g, {0: (-1, 0, 0), 1: (1, 0, 0), 2: (0, 0, 0), 3: (0, 1, 0), 4: (0, -1, 0)})


def _t_junction_and_closed_pair_graph() -> PositionedZX:
    # a component with both a port and closed leaves + a fully closed component
    g = GraphS()
    g.add_vertices(6)
    g.set_type(1, VertexType.X)
    for v in range(2, 6):
        g.set_type(v, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (1, 3), (4, 5)])
    return _positioned(
        g, {0: (-1, 0, 0), 1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0), 4: (0, 0, 2), 5: (1, 0, 2)}
    )


@pytest.mark.parametrize(
    ("graph_builder", "orderings"),
    [
        pytest.param(
            _hadamard_chain_graph,
            [
                [{0, 1}, {2, 3}],
                [{2, 3}, {0, 1}],
                [{0}, {1}, {2}, {3}],
                [{0, 3}, {1, 2}],
                [{0, 1, 2, 3}],
            ],
            id="hadamard_chain",
        ),
        pytest.param(
            _disconnected_graph_with_impossible_component,
            [[{0, 1}, {2, 3}], [{0, 2}, {1, 3}], [{0}, {1}, {2}, {3}]],
            id="disconnected_with_impossible_component",
        ),
        pytest.param(
            _circle_with_leaf_graph,
            [
                [{0, 1, 2, 5}, {3, 4}],
                [{3, 4}, {0, 1, 2, 5}],
                [{5}, {4}, {3}, {2}, {1}, {0}],
                [{0, 3}, {1, 4}, {2, 5}],
            ],
            id="circle_with_leaf",
        ),
        pytest.param(
            _hadamard_cycle_graph,
            [
                [{0, 1, 2}, {3, 4, 5}],
                [{0}, {1}, {2}, {3}, {4}, {5}],
                [{0, 4}, {1, 5}, {2, 3}],
            ],
            id="hadamard_cycle",
        ),
        pytest.param(
            _s_gate_teleportation_graph,
            [
                [{0, 1}, {2, 3, 4}],
                [{4}, {3}, {1}, {0, 2}],
                [{0, 2, 4}, {1, 3}],
            ],
            id="s_gate_teleportation",
        ),
        pytest.param(
            _hub_with_ports_and_closed_leaves_graph,
            [
                [{0, 1}, {2, 3, 4}],
                [{3, 4}, {2}, {0, 1}],
                [{0}, {1}, {2}, {3}, {4}],
            ],
            id="hub_with_ports_and_closed_leaves",
        ),
        pytest.param(
            _t_junction_and_closed_pair_graph,
            [
                [{0, 1, 2, 3}, {4, 5}],
                [{0, 4}, {1, 5}, {2, 3}],
                [{4}, {5}, {3}, {2}, {1}, {0}],
            ],
            id="t_junction_and_closed_pair",
        ),
    ],
)
def test_correlation_surfaces_with_vertex_ordering(
    graph_builder: Callable[[], PositionedZX], orderings: list[list[set[int]]]
) -> None:
    _assert_vertex_ordering_matches_default(graph_builder(), orderings)


@pytest.mark.parametrize("graph_builder", [cnot, move_rotation, steane_encoding])
def test_correlation_surfaces_with_vertex_ordering_on_block_graphs(
    graph_builder: Callable[[], BlockGraph],
) -> None:
    zx_graph = graph_builder().to_zx_graph()
    g = zx_graph.g
    time_slices: dict[int, set[int]] = {}
    for position, v in zx_graph.p2v.items():
        time_slices.setdefault(position.z, set()).add(v)
    ordering = [time_slices[z] for z in sorted(time_slices)]
    vertices = sorted(g.vertices())
    interleaved = [set(vertices[::2]), set(vertices[1::2])]
    _assert_vertex_ordering_matches_default(zx_graph, [ordering, ordering[::-1], interleaved])


def _four_node_circle_graph() -> PositionedZX:
    g = GraphS()
    g.add_vertices(5)
    for i in range(1, 5):
        g.set_type(i, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (2, 3), (3, 4), (1, 4)])
    # the 1-2-3-4 cycle is a unit square, with leaf 0 dangling off vertex 1
    return _positioned(g, {0: (-1, 0, 0), 1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0)})


def _strands_on_edge(
    surface: CorrelationSurface, u: Position3D, v: Position3D
) -> frozenset[ZXEdge]:
    return frozenset(edge for edge in surface.span if {edge.u.position, edge.v.position} == {u, v})


def _assert_contains_exactly(surface: CorrelationSurface, partial: CorrelationSurface) -> None:
    """Check the surface has exactly the partial surface's strands on the edges it spans."""
    for u, v in {(edge.u.position, edge.v.position) for edge in partial.span}:
        assert _strands_on_edge(surface, u, v) == _strands_on_edge(partial, u, v)


@pytest.mark.parametrize("bases", [{Basis.X}, {Basis.Z}, {Basis.X, Basis.Z}])
def test_find_correlation_surface_containing_forced_on_chain(bases: set[Basis]) -> None:
    # port - Z - Z - port: pinning the middle edge determines the surface uniquely
    g = GraphS()
    g.add_vertices(4)
    g.set_type(1, VertexType.Z)
    g.set_type(2, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (2, 3)])
    pg = _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (2, 0, 0), 3: (3, 0, 0)})
    partial = CorrelationSurface(
        frozenset(ZXEdge(ZXNode(pg[1], b), ZXNode(pg[2], b)) for b in bases)
    )
    surface = find_correlation_surface_containing(pg, partial)
    assert surface == CorrelationSurface(
        frozenset(ZXEdge(ZXNode(pg[u], b), ZXNode(pg[u + 1], b)) for u in range(3) for b in bases)
    )


def test_find_correlation_surface_containing_recovers_cycle_surface() -> None:
    # The Z broadcast around the circle is invisible at the only leaf, so it is not among the
    # generators returned by ``find_correlation_surfaces``, but it is the unique surface with
    # exactly a Z on the pinned circle edge and must be found as the completion.
    pg = _four_node_circle_graph()
    partial = CorrelationSurface(
        frozenset([ZXEdge(ZXNode(pg[2], Basis.Z), ZXNode(pg[3], Basis.Z))])
    )
    surface = find_correlation_surface_containing(pg, partial)
    assert surface == CorrelationSurface(
        frozenset(
            ZXEdge.sorted(ZXNode(pg[u], Basis.Z), ZXNode(pg[v], Basis.Z))
            for u, v in [(1, 2), (2, 3), (3, 4), (1, 4)]
        )
    )


def test_find_correlation_surface_containing_exact_match_is_strict() -> None:
    pg = _s_gate_teleportation_graph()
    # the edge to the Y spider can only support I or Y: a lone X strand cannot be completed
    x_only = CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[3], Basis.X), ZXNode(pg[4], Basis.X))]))
    assert find_correlation_surface_containing(pg, x_only) is None
    y = CorrelationSurface(frozenset(ZXEdge(ZXNode(pg[3], b), ZXNode(pg[4], b)) for b in Basis))
    surface = find_correlation_surface_containing(pg, y)
    assert surface is not None
    _check_correlation_surface_validity(surface, pg)
    _assert_contains_exactly(surface, y)


def test_find_correlation_surface_containing_unsatisfiable() -> None:
    # a closed Z-Z pair only supports the X broadcast on its edge
    g = GraphS()
    g.add_vertices(2)
    g.set_type(0, VertexType.Z)
    g.set_type(1, VertexType.Z)
    g.add_edge((0, 1))
    pg = _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0)})
    z = CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[0], Basis.Z), ZXNode(pg[1], Basis.Z))]))
    assert find_correlation_surface_containing(pg, z) is None
    x = CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[1], Basis.X))]))
    assert find_correlation_surface_containing(pg, x) == x


def test_find_correlation_surface_containing_disconnected_components() -> None:
    # two disjoint Z-Z pairs
    g = GraphS()
    g.add_vertices(4)
    for v in range(4):
        g.set_type(v, VertexType.Z)
    g.add_edges([(0, 1), (2, 3)])
    pg = _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (0, 1, 0), 3: (1, 1, 0)})
    x0 = ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[1], Basis.X))
    x2 = ZXEdge(ZXNode(pg[2], Basis.X), ZXNode(pg[3], Basis.X))
    # a partial surface on one component is completed without touching the other component
    one = CorrelationSurface(frozenset([x0]))
    assert find_correlation_surface_containing(pg, one) == one
    # a partial surface spanning both components is completed on both
    both = CorrelationSurface(frozenset([x0, x2]))
    assert find_correlation_surface_containing(pg, both) == both


@pytest.mark.parametrize("graph_builder", [cnot, steane_encoding])
def test_find_correlation_surface_containing_partials_of_found_surfaces(
    graph_builder: Callable[[], BlockGraph],
) -> None:
    pg = graph_builder().to_zx_graph()
    for surface in find_correlation_surfaces(pg):
        # keep only the strands on the two smallest spanned edges as the partial surface
        edges = sorted({tuple(sorted((e.u.position, e.v.position))) for e in surface.span})[:2]
        partial = CorrelationSurface(
            frozenset(
                e for e in surface.span if tuple(sorted((e.u.position, e.v.position))) in edges
            )
        )
        completion = find_correlation_surface_containing(pg, partial)
        assert completion is not None
        _check_correlation_surface_validity(completion, pg)
        _assert_contains_exactly(completion, partial)


def test_find_correlation_surface_containing_invalid_inputs() -> None:
    pg = _hadamard_chain_graph()
    with pytest.raises(TQECError, match="at least one edge"):
        find_correlation_surface_containing(pg, CorrelationSurface(frozenset()))
    not_an_edge = CorrelationSurface(
        frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[2], Basis.X))])
    )
    with pytest.raises(TQECError, match="not in the graph"):
        find_correlation_surface_containing(pg, not_an_edge)
    # the same basis on the two half-edges of a hadamard edge is inconsistent
    inconsistent = CorrelationSurface(
        frozenset([ZXEdge(ZXNode(pg[1], Basis.X), ZXNode(pg[2], Basis.X))])
    )
    with pytest.raises(TQECError, match="inconsistent with the edge type"):
        find_correlation_surface_containing(pg, inconsistent)
    valid = CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[1], Basis.X))]))
    with pytest.raises(TQECError, match="must partition"):
        find_correlation_surface_containing(pg, valid, vertex_ordering=[{0, 1}, {2}])
    surface = find_correlation_surface_containing(pg, valid, vertex_ordering=[{0, 1}, {2, 3}])
    assert surface is not None
    _assert_contains_exactly(surface, valid)


def test_find_correlation_surfaces_with_invalid_vertex_ordering() -> None:
    pg = _hadamard_chain_graph()
    # overlapping parts
    with pytest.raises(TQECError, match="must partition"):
        find_correlation_surfaces(pg, vertex_ordering=[{0, 1}, {1, 2, 3}])
    # missing vertices
    with pytest.raises(TQECError, match="must partition"):
        find_correlation_surfaces(pg, vertex_ordering=[{0, 1}, {2}])
    # vertices not in the graph
    with pytest.raises(TQECError, match="must partition"):
        find_correlation_surfaces(pg, vertex_ordering=[{0, 1}, {2, 3, 4}])


@pytest.mark.parametrize("graph_builder", [cnot, steane_encoding])
def test_block_graph_find_correlation_surfaces_partition_along_time(
    graph_builder: Callable[[], BlockGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = graph_builder()
    pg = bg.to_zx_graph()
    g = pg.g
    leaf_vertices = sorted(v for v in g.vertices() if g.vertex_degree(v) == 1)
    leaves = [pg[v] for v in leaf_vertices]
    open_leaves = [pg[v] for v in leaf_vertices if g.type(v) is VertexType.BOUNDARY]
    default = bg.find_correlation_surfaces(partition_along_time=False)
    sliced = bg.find_correlation_surfaces(partition_along_time=True)
    for surface in sliced:
        _check_correlation_surface_validity(surface, pg)
    assert len(sliced) == len(default)
    assert len(_signature_span(sliced, leaves)) == len(sliced)
    assert _signature_span(sliced, open_leaves) == _signature_span(default, open_leaves)
    # the gallery graphs are below the automatic leaf-cube threshold: the default search is used
    assert bg.find_correlation_surfaces() == default
    # lowering the threshold enables the time slicing automatically
    monkeypatch.setattr(block_graph_module, "_PARTITION_ALONG_TIME_MIN_LEAF_CUBES", 1)
    automatic = bg.find_correlation_surfaces()
    assert len(automatic) == len(default)
    assert _signature_span(automatic, open_leaves) == _signature_span(default, open_leaves)


def test_find_correlation_surface_containing_single_node() -> None:
    g = GraphS()
    g.add_vertex(VertexType.X)
    pg = _positioned(g, {0: (0, 0, 0)})
    surface = find_correlation_surfaces(pg)[0]
    assert find_correlation_surface_containing(pg, surface) == surface
    other = CorrelationSurface(frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[0], Basis.X))]))
    assert find_correlation_surface_containing(pg, other) is None


def test_find_correlation_surface_containing_with_vertex_ordering() -> None:
    pg = _four_node_circle_graph()
    g = pg.g
    z_cycle = CorrelationSurface(
        frozenset(
            ZXEdge.sorted(ZXNode(pg[u], Basis.Z), ZXNode(pg[v], Basis.Z))
            for u, v in [(1, 2), (2, 3), (3, 4), (1, 4)]
        )
    )
    pin_z = {(2, 3): Pauli.Z, (3, 2): Pauli.Z}
    # pinning the port edge to Z is unsatisfiable: only I or X can flow through it
    pin_unsat = {(0, 1): Pauli.Z, (1, 0): Pauli.Z}
    orderings = [None, [{0, 1, 2}, {3, 4}], [{2, 4}, {0, 1, 3}], [{0}, {1}, {2}, {3}, {4}]]
    for ordering in orderings:
        surface = _find_correlation_surface_containing(g, pin_z, ordering)
        assert surface is not None
        assert surface.to_immutable_public_representation(pg) == z_cycle
        assert _find_correlation_surface_containing(g, pin_unsat, ordering) is None


def test_find_correlation_surface_containing_on_leafless_cycle() -> None:
    # ``find_correlation_surfaces`` rejects a graph without any leaf, but a completion query
    # cuts the pinned edge open and can still be answered
    g = GraphS()
    g.add_vertices(4)
    for v in range(4):
        g.set_type(v, VertexType.Z)
    g.add_edges([(0, 1), (1, 2), (2, 3), (0, 3)])
    pg = _positioned(g, {0: (0, 0, 0), 1: (1, 0, 0), 2: (1, 1, 0), 3: (0, 1, 0)})
    with pytest.raises(TQECError):
        find_correlation_surfaces(pg)
    partial = CorrelationSurface(
        frozenset([ZXEdge(ZXNode(pg[0], Basis.X), ZXNode(pg[1], Basis.X))])
    )
    surface = find_correlation_surface_containing(pg, partial)
    assert surface == CorrelationSurface(
        frozenset(
            ZXEdge.sorted(ZXNode(pg[u], Basis.X), ZXNode(pg[v], Basis.X))
            for u, v in [(0, 1), (1, 2), (2, 3), (0, 3)]
        )
    )
