"""Defines the ``CorrelationSurface`` class and the functions to find the
correlation surfaces in the ZX graph."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Iterator, TYPE_CHECKING

from pyzx.graph.graph_s import GraphS

from tqec.utils.enums import Basis

if TYPE_CHECKING:
    from pyzx.pauliweb import PauliWeb


@dataclass(frozen=True, order=True)
class ZXNode:
    """Represent a node in the ZX graph spanned by the correlation surface.

    Correlation surface is represented by a set of edges in the ZX graph. Each edge
    consists of two nodes. The node id refers to the vertex index in the graph
    and the basis represents the Pauli operator on the half edge incident to the node.

    Attributes:
        id: The index of the vertex in the graph.
        basis: The Pauli operator on the half edge incident to the node.
    """

    id: int
    basis: Basis


@dataclass(frozen=True, order=True)
class ZXEdge:
    """Represent an edge in the ZX graph spanned by the correlation surface.

    Correlation surface is represented by a set of edges in the ZX graph. Each edge
    consists of two nodes. The edge can be decomposed into two half edges, each
    incident to a node. The half edges are labeled with the Pauli operator.
    If the edge has no hadamard effect, the Pauli operators on the two half edges
    should be the same. Otherwise, the Pauli operators should be flipped.

    Note that the Pauli operators are represented by `Basis` enum, which only
    contains `X` and `Z` operators. The `Y` operator is represented by two
    edges with `X` and `Z` operators respectively.
    """

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
        """Whether the edge is a self-loop edge.

        By definition, a self-loop edge represents a correlation surface
        within a single node. This is an edge case where the ZX graph
        only contains a single node.
        """
        return self.u.id == self.v.id

    @property
    def has_hadamard(self) -> bool:
        """Whether the edge has a hadamard effect."""
        return self.u.basis != self.v.basis


@dataclass(frozen=True)
class CorrelationSurface:
    """A correlation surface in a computation is a set of measurements whose
    values determine the parity of the logical operators at the inputs and
    outputs associated with the surface.

    Note:
        We use the term "correlation surface", "pauli web" and "observable" interchangeably in
        the library.

    Here we represent the correlation surface by the set of edges it spans in the ZX graph.
    The insight is that the spiders pose parity constraints on the operators supported on
    the incident edges. The flow of the logical operators through the ZX graph, respecting
    the parity constraints, forms the correlation between the inputs and outputs. However,
    the sign of measurement outcomes is neglected in this representation. And we need to
    recover the measurements when instantiating an explicit logical observable from the
    correlation surface.

    Each edge establishes a correlation between the logical operators at the two ends of
    the edge. For example, an edge connecting two Z nodes represents the correlation
    between the logical Z operators at the two nodes.

    Attributes:
        span: A set of ``ZXEdge`` representing the span of the correlation surface.
    """

    span: frozenset[ZXEdge]

    def bases_at(self, v: int) -> set[Basis]:
        """Get the bases of the surfaces present at the vertex."""
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
    def from_pauli_web(pauli_web: PauliWeb[int, tuple[int, int]]) -> CorrelationSurface:
        """Create a correlation surface from a Pauli web."""
        from tqec.interop.pyzx.correlation import pauli_web_to_correlation_surface

        return pauli_web_to_correlation_surface(pauli_web)

    @property
    def is_single_node(self) -> bool:
        """Whether the correlation surface contains only a single node.

        This is an edge case where the ZX graph only contains a single
        node. The span of the correlation surface is a self-loop edge at
        the node.
        """
        return len(self.span) == 1 and next(iter(self.span)).is_self_loop()

    def span_vertices(self) -> set[int]:
        """Return the set of vertices in the correlation surface."""
        return {v.id for edge in self.span for v in edge}

    def edges_at(self, v: int) -> set[ZXEdge]:
        """Return the set of edges incident to the vertex in the correlation
        surface."""
        return {edge for edge in self.span if any(n.id == v for n in edge)}

    def external_stabilizer(self, io_ports: list[int]) -> str:
        """Get the Pauli operator supported on the given input/output ports.

        Args:
            io_ports: The list of input/output ports to consider.

        Returns:
            The Pauli operator supported on the given ports.
        """
        from pyzx.pauliweb import multiply_paulis

        paulis = [
            reduce(multiply_paulis, {b.value for b in self.bases_at(port)}, "I")
            for port in io_ports
        ]
        return "".join(paulis)
