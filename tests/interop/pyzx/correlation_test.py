from tqec.compile.observables.abstract_observable import _check_correlation_surface_validity
from tqec.computation.correlation import CorrelationSurface, find_correlation_surfaces
from tqec.gallery import steane_encoding


def test_correlation_pauliweb_conversion() -> None:
    g = steane_encoding().to_zx_graph().g
    surfaces = find_correlation_surfaces(g)
    for surface in surfaces:
        _check_correlation_surface_validity(surface, g)
        pauli_web = surface.to_pauli_web(g)
        assert CorrelationSurface.from_pauli_web(pauli_web) == surface
