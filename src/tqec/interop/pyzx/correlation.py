"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb

from tqec.computation._correlation import _CorrelationSurface
from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import is_hadamard, vertex_type_to_pauli
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
    # pyzx's PauliWeb does not support self-loop half-edges, so single-node
    # correlation surfaces (which have no graph edges) cannot be encoded in a
    # PauliWeb.  Reconstruct them directly from the vertex type.
    zx_graph = g.g
    vertices = list(zx_graph.vertices())
    if len(vertices) == 1 and not list(zx_graph.edges()):
        u = vertices[0]
        pos = g[u]
        basis = vertex_type_to_pauli(zx_graph.type(u)).to_basis().flipped()
        node = ZXNode(pos, basis)
        return CorrelationSurface(frozenset([ZXEdge.sorted(node, node)]))
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
    processed_edges: set[tuple[int, int]] = set()
    for u, v in zx_graph.edges():
        surface._add_pauli_to_edge(
            (u, v),
            Pauli[half_edges.get((u, v), "I")],
            is_hadamard(zx_graph, (u, v)),  # type: ignore
        )
        processed_edges.add((v, u))
    return surface
