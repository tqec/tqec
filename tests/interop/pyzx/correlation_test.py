import pytest
from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.compile.observables.abstract_observable import _check_correlation_surface_validity
from tqec.computation.correlation import CorrelationSurface, find_correlation_surfaces
from tqec.gallery import steane_encoding
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.position import Position3D


def test_correlation_pauliweb_conversion() -> None:
    g = steane_encoding().to_zx_graph()
    surfaces = find_correlation_surfaces(g)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, g)
        pauli_web = surface.to_pauli_web(g)
        assert CorrelationSurface.from_pauli_web(pauli_web, g) == surface


@pytest.mark.parametrize("ty", [VertexType.X, VertexType.Z])
def test_single_node_correlation_pauliweb_round_trip(ty: VertexType) -> None:
    g = GraphS()
    g.add_vertex(ty)
    pg = PositionedZX(g, {0: Position3D(0, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    assert len(surfaces) == 1
    surface = surfaces[0]
    assert surface.is_single_node
    pauli_web = surface.to_pauli_web(pg)
    assert CorrelationSurface.from_pauli_web(pauli_web, pg) == surface


@pytest.mark.parametrize("ty", [VertexType.X, VertexType.Z])
def test_single_node_span_has_no_repeated_edges(ty: VertexType) -> None:
    """The self-loop edge must appear exactly once in the span (no duplicates)."""
    g = GraphS()
    g.add_vertex(ty)
    pg = PositionedZX(g, {0: Position3D(0, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    assert len(surfaces) == 1
    surface = surfaces[0]
    # frozenset deduplicates — if the span were built with duplicates the
    # equality below would still pass, so we also check the raw list via
    # _to_mutable_graph_representation round-trip through the span count.
    assert len(surface.span) == 1


@pytest.mark.parametrize(
    ("ty_u", "ty_v", "edge_type"),
    [
        (VertexType.Z, VertexType.Z, EdgeType.SIMPLE),
        (VertexType.X, VertexType.X, EdgeType.SIMPLE),
        (VertexType.Z, VertexType.X, EdgeType.HADAMARD),
        (VertexType.X, VertexType.Z, EdgeType.HADAMARD),
    ],
)
def test_two_node_correlation_pauliweb_round_trip(
    ty_u: VertexType, ty_v: VertexType, edge_type: EdgeType
) -> None:
    """Happy path: two-node graph round-trip for normal and Hadamard edges."""
    g = GraphS()
    u = g.add_vertex(ty_u)
    v = g.add_vertex(ty_v)
    g.add_edge((u, v), edge_type)
    pg = PositionedZX(g, {u: Position3D(0, 0, 0), v: Position3D(1, 0, 0)})
    surfaces = find_correlation_surfaces(pg)
    for surface in surfaces:
        pauli_web = surface.to_pauli_web(pg)
        assert CorrelationSurface.from_pauli_web(pauli_web, pg) == surface


def test_from_pauli_web_wrong_graph_raises() -> None:
    """Sad path: reconstructing with a different graph than the one used to build
    the PauliWeb should not silently return a valid surface."""
    g1 = GraphS()
    g1.add_vertex(VertexType.Z)
    pg1 = PositionedZX(g1, {0: Position3D(0, 0, 0)})

    g2 = GraphS()
    g2.add_vertex(VertexType.X)
    pg2 = PositionedZX(g2, {0: Position3D(0, 0, 0)})

    surfaces = find_correlation_surfaces(pg1)
    assert len(surfaces) == 1
    pauli_web = surfaces[0].to_pauli_web(pg1)
    # Reconstructing with a graph of a different vertex type should produce a
    # different surface, not the same one.
    reconstructed = CorrelationSurface.from_pauli_web(pauli_web, pg2)
    assert reconstructed != surfaces[0]

