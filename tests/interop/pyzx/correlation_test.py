import pytest
from pyzx.graph.graph_s import GraphS
from pyzx.utils import VertexType

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
