"""Defines :class:`CorrelationSurface` and functions to find and build them from a ZX graph."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tqec.computation.block_graph import BlockGraph
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D

if TYPE_CHECKING:
    from pyzx.graph.graph_s import GraphS
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

        By definition, a self-loop edge represents a correlation surface within a single node. This
        is an edge case where the ZX graph only contains a single node.

        """
        return self.u.id == self.v.id

    @property
    def has_hadamard(self) -> bool:
        """Whether the edge has a hadamard effect."""
        return self.u.basis != self.v.basis


@dataclass(frozen=True)
class CorrelationSurface:
    """Represent a set of measurements whose values determine the parity of the logical operators.

    A correlation surface in a computation is a set of measurements whose values determine the
    parity of the logical operators at the inputs and outputs associated with the surface.

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
        # Avoid pulling pyzx when importing that module.
        from tqec.interop.pyzx.correlation import correlation_surface_to_pauli_web  # noqa: PLC0415

        return correlation_surface_to_pauli_web(self, g)

    @staticmethod
    def from_pauli_web(pauli_web: PauliWeb[int, tuple[int, int]]) -> CorrelationSurface:
        """Create a correlation surface from a Pauli web."""
        # Avoid pulling pyzx when importing that module.
        from tqec.interop.pyzx.correlation import pauli_web_to_correlation_surface  # noqa: PLC0415

        return pauli_web_to_correlation_surface(pauli_web)

    @property
    def is_single_node(self) -> bool:
        """Whether the correlation surface contains only a single node.

        This is an edge case where the ZX graph only contains a single node. The span of the
        correlation surface is a self-loop edge at the node.

        """
        return len(self.span) == 1 and next(iter(self.span)).is_self_loop()

    def span_vertices(self) -> set[int]:
        """Return the set of vertices in the correlation surface."""
        return {v.id for edge in self.span for v in edge}

    def edges_at(self, v: int) -> set[ZXEdge]:
        """Return the set of edges incident to the vertex in the correlation surface."""
        return {edge for edge in self.span if any(n.id == v for n in edge)}

    def external_stabilizer(self, io_ports: list[int]) -> str:
        """Get the Pauli operator supported on the given input/output ports.

        Args:
            io_ports: The list of input/output ports to consider.

        Returns:
            The Pauli operator supported on the given ports.

        """
        # Avoid pulling pyzx when importing that module.
        from pyzx.pauliweb import multiply_paulis  # noqa: PLC0415

        paulis = []
        for port in io_ports:
            basis_set = {b.value for b in self.bases_at(port)}
            result = "I"
            for basis in basis_set:
                result = multiply_paulis(result, basis)
            paulis.append(result)

        return "".join(paulis)

    def external_stabilizer_on_graph(self, graph: BlockGraph) -> str:
        """Get the external stabilizer of the correlation surface on the graph.

        If the provided graph is an open graph, the external stabilizer is the Pauli
        operator supported on the input/output ports of the graph. Otherwise, the
        external stabilizer is the Pauli operator supported on the leaf nodes of the
        graph.

        Args:
            graph: The block graph to consider.

        Returns:
            The Pauli operator that is the external stabilizer of the correlation surface.

        """
        supports: list[Position3D]
        if graph.is_open:
            port_labels = graph.ordered_ports
            supports = [graph.ports[p] for p in port_labels]
        else:
            supports = [cube.position for cube in graph.leaf_cubes]
        zx = graph.to_zx_graph()
        p2v = zx.p2v
        zx_ports = [p2v[p] for p in supports]
        return self.external_stabilizer(zx_ports)

    def area(self) -> int:
        """Return the area of the correlation surface.

        The area of the correlation surface is the number of nodes it spans. A X node and a Z node
        with the same id are counted as two nodes.

        """
        span_nodes = {node for edge in self.span for node in edge}
        return len(span_nodes)

    def __xor__(self, other: CorrelationSurface) -> CorrelationSurface:
        return CorrelationSurface(self.span.symmetric_difference(other.span))
