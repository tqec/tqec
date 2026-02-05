"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb

from tqec.computation._correlation import _CorrelationSurface
from tqec.computation.correlation import CorrelationSurface
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import is_hadamard
from tqec.utils.enums import Pauli


def correlation_surface_to_pauli_web(
    correlation_surface: CorrelationSurface, g: PositionedZX
) -> PauliWeb[int, tuple[int, int]]:
    """Convert the correlation surface to a Pauli web.

    Args:
        correlation_surface: The correlation surface to convert.
        g: The PositionedZX graph the correlation surface is based on.

    Returns:
        A `PauliWeb` representation of the correlation surface.

    """
    return _correlation_surface_to_pauli_web(
        correlation_surface._to_mutable_graph_representation(g), g.g
    )


def pauli_web_to_correlation_surface(
    pauli_web: PauliWeb[int, tuple[int, int]], g: PositionedZX
) -> CorrelationSurface:
    """Create a correlation surface from a Pauli web."""
    return _pauli_web_to_correlation_surface(pauli_web)._to_immutable_public_representation(g)


def _correlation_surface_to_pauli_web(
    correlation_surface: _CorrelationSurface, g: GraphS
) -> PauliWeb[int, tuple[int, int]]:
    pauli_web = PauliWeb(g)
    for u, edges in correlation_surface.items():
        for v, pauli in edges.items():
            pauli_web.add_half_edge((u, v), str(pauli))
    return pauli_web


def _pauli_web_to_correlation_surface(
    pauli_web: PauliWeb[int, tuple[int, int]],
) -> _CorrelationSurface:
    zx_graph = pauli_web.g
    surface = _CorrelationSurface()
    half_edges: dict[tuple[int, int], str] = pauli_web.half_edges()
    for (u, v), pauli in half_edges.items():
        surface._add_pauli_to_edge((u, v), Pauli[pauli], is_hadamard(zx_graph, (u, v)))
        half_edges.pop((v, u), None)
    return surface
