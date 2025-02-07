"""Defines the ``CorrelationSurface`` class and the functions to find the
correlation surfaces in the ZX graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, TYPE_CHECKING

from pyzx.graph.graph_s import GraphS

from tqec.utils.enums import Basis

if TYPE_CHECKING:
    from pyzx.pauliweb import PauliWeb


@dataclass(frozen=True, order=True)
class ZXNode:
    id: int
    basis: Basis


@dataclass(frozen=True, order=True)
class ZXEdge:
    u: ZXNode
    v: ZXNode

    def __post_init__(self) -> None:
        if self.u.id > self.v.id:
            u, v = self.v, self.u
            object.__setattr__(self, "u", u)
            object.__setattr__(self, "v", v)

    def __iter__(self) -> Iterator[ZXNode]:
        yield self.u
        yield self.v

    def is_self_loop(self) -> bool:
        return self.u.id == self.v.id

    @property
    def has_hadamard(self) -> bool:
        return self.u.basis != self.v.basis


@dataclass(frozen=True)
class CorrelationSurface:
    span: frozenset[ZXEdge]

    def bases_at(self, v: int) -> set[Basis]:
        """Get the bases of the present surfaces at the vertex."""
        edges = self.edges_at(v)
        bases = set()
        for edge in edges:
            if edge.u.id == v:
                bases.add(edge.u.basis)
            else:
                bases.add(edge.v.basis)
        return bases

    def to_pauli_web(self, g: GraphS) -> PauliWeb[int, tuple[int, int]]:
        """Convert the correlation surface to a Pauli web.

        Args:
            g: The ZX graph the correlation surface is based on.

        Returns:
            A `PauliWeb` representation of the correlation surface.
        """
        from tqec.interop.pyzx.correlation import correlation_surface_to_pauli_web

        return correlation_surface_to_pauli_web(self, g)

    @staticmethod
    def from_pauli_web(pauli_web: PauliWeb) -> CorrelationSurface:
        """Create a correlation surface from a Pauli web."""
        from tqec.interop.pyzx.correlation import pauli_web_to_correlation_surface

        return pauli_web_to_correlation_surface(pauli_web)

    @property
    def is_single_node(self) -> bool:
        """Whether the correlation surface contains only a single node.
        This is an edge case where the ZX graph only contains a single node.
        The span of the correlation surface is a self-loop edge at the node.
        """
        return len(self.span) == 1 and next(iter(self.span)).is_self_loop()

    def span_vertices(self) -> set[int]:
        """Return the set of vertices in the correlation surface."""
        return {v.id for edge in self.span for v in edge}

    def edges_at(self, v: int) -> set[ZXEdge]:
        """Return the set of edges incident to the vertex in the correlation surface."""
        return {edge for edge in self.span if any(n.id == v for n in edge)}
