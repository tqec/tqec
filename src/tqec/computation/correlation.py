"""Defines :class:`CorrelationSurface` and functions to find and build them from a ZX graph."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property, reduce
from itertools import chain
from operator import xor
from typing import TYPE_CHECKING, NamedTuple

import stim

from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

if TYPE_CHECKING:
    from pyzx.graph.graph_s import GraphS
    from pyzx.pauliweb import PauliWeb

    from tqec.computation._correlation import _CorrelationSurface
    from tqec.computation.block_graph import BlockGraph


class ZXNode(NamedTuple):
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


class ZXEdge(NamedTuple):
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

    @staticmethod
    def sorted(u: ZXNode, v: ZXNode) -> ZXEdge:
        """Create a ZXEdge with nodes sorted."""
        return ZXEdge(*tuple(sorted([u, v])))

    @property
    def is_self_loop(self) -> bool:
        """Whether the edge is a self-loop edge.

        By definition, a self-loop edge represents a correlation surface within a single node. This
        is an edge case where the ZX graph only contains a single node.

        """
        return self.u.id == self.v.id

    @property
    def has_hadamard(self) -> bool:
        """Whether the edge has a hadamard effect."""
        return self.u.basis is not self.v.basis

    def get_basis(self, vertex_id: int) -> Basis:
        """Get the basis of the half edge incident to the given vertex."""
        match vertex_id:
            case self.u.id:
                return self.u.basis
            case self.v.id:
                return self.v.basis
            case _:
                raise TQECError(f"Vertex {vertex_id} is not incident to the edge {self}.")


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

    @cached_property
    def _graph_view(self) -> tuple[dict[int, dict[int, list[ZXEdge]]], dict[int, set[Basis]]]:
        """Internal index mapping vertex IDs to active bases and incident edges."""
        edges, bases = {}, {}
        for edge in self.span:
            u, v = edge.u.id, edge.v.id
            edges.setdefault(u, {}).setdefault(v, []).append(edge)
            edges.setdefault(v, {}).setdefault(u, []).append(edge)
            bases.setdefault(u, set()).add(edge.u.basis)
            bases.setdefault(v, set()).add(edge.v.basis)
        return edges, bases

    def bases_at(self, v: int) -> set[Basis]:
        """Get the bases of the surfaces present at the vertex."""
        return self._graph_view[1].get(v, set())

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
        return len(self.span) == 1 and next(iter(self.span)).is_self_loop

    @property
    def span_vertices(self) -> set[int]:
        """Return the set of vertices in the correlation surface."""
        return set(self._graph_view[0].keys())

    def edges_at(self, v: int) -> set[ZXEdge]:
        """Return the set of edges incident to the vertex in the correlation surface."""
        return set(chain.from_iterable(self._graph_view[0].get(v, {}).values()))

    def external_stabilizer(self, io_ports: list[int]) -> str:
        """Get the Pauli operator supported on the given input/output ports.

        Args:
            io_ports: The list of input/output ports to consider.

        Returns:
            The Pauli operator supported on the given ports.

        """
        return "".join(str(Pauli.from_basis_set(self.bases_at(port))) for port in io_ports)

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

    @cached_property
    def area(self) -> int:
        """Return the area of the correlation surface.

        The area of the correlation surface is the number of nodes it spans. A X node and a Z node
        with the same id are counted as two nodes.

        """
        span_nodes = {node for edge in self.span for node in edge}
        return len(span_nodes)

    def __xor__(self, other: CorrelationSurface) -> CorrelationSurface:
        return CorrelationSurface(self.span.symmetric_difference(other.span))

    def _to_mutable_graph_representation(self, zx_graph: GraphS) -> _CorrelationSurface:
        """Convert to the internal mutable representation."""
        # Avoid pulling pyzx when importing that module.
        from tqec.computation._correlation import (  # noqa: PLC0415
            _CorrelationSurface,
            _CorrelationSurfaceSpace,
        )
        from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

        surface = _CorrelationSurface(_CorrelationSurfaceSpace().register_graph(zx_graph))
        for u, edges in self._graph_view[0].items():
            for v, edge in edges.items():
                surface._add_pauli_to_edge(
                    (u, v),
                    reduce(xor, (e.get_basis(u).to_pauli() for e in edge)),
                    is_hadamard(zx_graph, (u, v)),
                )
        return surface


def _check_vertex_ordering_is_partition(g: GraphS, vertex_ordering: Sequence[set[int]]) -> None:
    """Check the vertex ordering partitions the graph vertices into disjoint covering sets."""
    union: set[int] = set()
    total_size = 0
    for part in vertex_ordering:
        union |= part
        total_size += len(part)
    if total_size != len(union) or union != g.vertex_set():
        raise TQECError(
            "`vertex_ordering` must partition the graph vertices into disjoint sets covering"
            " all the vertices."
        )


def find_correlation_surfaces(
    g: GraphS,
    vertex_ordering: Sequence[set[int]] | None = None,
    parallel: bool = True,
) -> list[CorrelationSurface]:
    """Find the correlation surfaces in a ZX graph.

    The function explores how can the X/Z logical observable move through the graph to form a
    correlation surface with the following steps:

    1. Identify connected components in the graph.
    2. For each connected component, run the following algorithm from the smallest leaf node to find
       a generating set of correlation surfaces assuming all ports are open:
         a. Explore the graph node-by-node while keeping a generating set of correlation surfaces
            for the subgraph explored.
         b. Generate valid correlation surfaces given the newly explored node.
         c. If there is a loop, recover valid correlation surfaces from invalid ones.
         d. Prune redundant ones to keep the generating set minimal.
         e. Repeat from step (a) until all nodes are explored.
    3. Reform the generators so that they satisfy the closed ports (non-BOUNDARY leaf nodes).
    4. Reform the generators so that the number of Y-terminating correlation surfaces is minimized.
    5. Combine the generators from all connected components.

    If ``vertex_ordering`` is provided, the above algorithm runs on each part separately and the
    per-part generators are glued at the cut edges by Gaussian elimination over GF(2), sweeping
    the parts in the given order.

    The rules for generating valid correlation surfaces at each node are as follows. For a node of
    basis B in {X, Z}:
    - *broadcast rule:* All or none of the incident edges supports the opposite of B.
    - *passthrough rule:* An even number of incident edges supports B.

    Leaf nodes can additionally be of both or none of the X and Z bases and also need to follow the
      above rules. Specifically:
    - For an X/Z type leaf node, it can only support the logical observable with the opposite type.
    - For a Y type leaf node, it can only support the Y logical observable, i.e. the presence of
      both X and Z logical observable.
    - For the BOUNDARY node, it can support any type of logical observable.

    Args:
        g: The ZX graph to find the correlation surfaces.
        vertex_ordering: An optional partition of the graph vertices into disjoint sets covering
            all the vertices, swept in the given order. The returned surfaces span the same
            correlations for any valid partition and ordering, but the generator representatives
            may differ from the default search. Partitions whose parts have small cuts, e.g. the
            time slices of a computation, speed up the search on graphs with many leaves and
            allow parallelism across the parts.
        parallel: Whether to use multiprocessing to speed up the computation. Only applies to
            embarrassingly parallel parts of the algorithm. Default is `True`.

    Returns:
        A list of `CorrelationSurface` in the graph.

    Raises:
        TQECError: If the graph contains an unsupported spider, has no leaf node, or if
            `vertex_ordering` is provided but does not partition the graph vertices.

    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _find_correlation_surfaces_with_vertex_ordering,
    )
    from tqec.interop.pyzx.utils import zx_to_basis  # noqa: PLC0415

    if vertex_ordering:
        _check_vertex_ordering_is_partition(g, vertex_ordering)
    _check_spiders_are_supported(g)
    # Edge case: single node graph
    if g.num_vertices() == 1:
        v = next(iter(g.vertices()))
        node = ZXNode(v, zx_to_basis(g, v).flipped())
        return [CorrelationSurface(frozenset({ZXEdge(node, node)}))]

    leaves = {v for v in g.vertices() if g.vertex_degree(v) == 1}
    if not leaves:
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )

    # sort the correlation surfaces by area
    return sorted(
        (
            cs._to_immutable_public_representation(g)
            for cs in _find_correlation_surfaces_with_vertex_ordering(g, vertex_ordering, parallel)
        ),
        key=lambda x: sorted(x.span),
    )


def find_correlation_surface_containing(
    g: GraphS,
    partial_surface: CorrelationSurface,
    vertex_ordering: Sequence[set[int]] | None = None,
    parallel: bool = True,
) -> CorrelationSurface | None:
    """Find a correlation surface in a ZX graph that contains the given partial surface.

    The partial surface is interpreted as an exact specification on the edges it spans: the
    returned surface supports exactly the same Pauli operator as the partial surface on each of
    these edges (e.g. an edge carrying only an X strand in the partial surface cannot carry Y
    in the returned surface) and is completed into a valid correlation surface on the other
    edges, where it is unconstrained.

    The completion is found by cutting each specified edge into a pair of dangling boundary
    nodes, finding the correlation surface generators of the cut graph, which keeps the
    resolution of the generating set at the specified edges, and identifying a combination of
    the generators with the required Pauli operators at the added boundary nodes by Gaussian
    elimination over GF(2).

    Args:
        g: The ZX graph to find the correlation surface in.
        partial_surface: The partial correlation surface, specified by the edges it spans in
            the graph. It does not need to satisfy the parity constraints at the graph nodes.
        vertex_ordering: An optional partition of the graph vertices into disjoint sets
            covering all the vertices, swept in the given order to find the correlation
            surface generators. See :func:`find_correlation_surfaces` for details.
        parallel: Whether to use multiprocessing to speed up the computation. Only applies to
            embarrassingly parallel parts of the algorithm. Default is `True`.

    Returns:
        A `CorrelationSurface` that contains the partial surface, or `None` if no valid
        correlation surface in the graph matches the partial surface on the edges it spans.

    Raises:
        TQECError: If the partial surface is empty, spans edges that are not in the graph,
            assigns Pauli operators inconsistent with the edge types, e.g. the same basis on
            the two half-edges of a Hadamard edge, or if `vertex_ordering` is provided but
            does not partition the graph vertices.

    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _find_correlation_surface_containing,
    )
    from tqec.interop.pyzx.utils import is_hadamard, zx_to_basis  # noqa: PLC0415

    if vertex_ordering:
        _check_vertex_ordering_is_partition(g, vertex_ordering)
    _check_spiders_are_supported(g)
    if not partial_surface.span:
        raise TQECError("The partial correlation surface must span at least one edge.")

    # Edge case: single node graph
    if g.num_vertices() == 1:
        v = next(iter(g.vertices()))
        node = ZXNode(v, zx_to_basis(g, v).flipped())
        surface = CorrelationSurface(frozenset({ZXEdge(node, node)}))
        if partial_surface.span == surface.span:
            return surface
        if any(edge.u.id != v or edge.v.id != v for edge in partial_surface.span):
            raise TQECError("The partial surface spans edges that are not in the graph.")
        return None

    # collect and validate the Pauli operators on the half-edges of the partial surface
    vertex_set = g.vertex_set()
    half_edge_paulis: dict[tuple[int, int], Pauli] = {}
    for zx_edge in partial_surface.span:
        (u, basis_u), (v, basis_v) = zx_edge.u, zx_edge.v
        if (
            zx_edge.is_self_loop
            or u not in vertex_set
            or v not in vertex_set
            or not g.connected(u, v)
        ):
            raise TQECError(f"Edge {(u, v)} of the partial surface is not in the graph.")
        half_edge_paulis[(u, v)] = half_edge_paulis.get((u, v), Pauli.I) ^ basis_u.to_pauli()
        half_edge_paulis[(v, u)] = half_edge_paulis.get((v, u), Pauli.I) ^ basis_v.to_pauli()
    for (u, v), pauli in half_edge_paulis.items():
        if half_edge_paulis[(v, u)] is not pauli.flipped(is_hadamard(g, (u, v))):
            raise TQECError(
                f"The Pauli operators of the partial surface on the edge {(u, v)} are"
                " inconsistent with the edge type."
            )

    surface = _find_correlation_surface_containing(g, half_edge_paulis, vertex_ordering, parallel)
    return surface._to_immutable_public_representation(g) if surface is not None else None


def reduce_observables_to_minimal_generators(
    stabilizers_to_surfaces: dict[str, CorrelationSurface],
    hint_num_generators: int | None = None,
) -> dict[str, CorrelationSurface]:
    """Reduce a set of observables to generators with the smallest correlation surface area.

    Args:
        stabilizers_to_surfaces: The mapping from the stabilizer to the correlation surface.
        hint_num_generators: The hint number of generators to find. If provided,
            the function will stop after finding the specified number of generators.
            Otherwise, the function will iterate through all the stabilizers.

    Returns:
        A mapping from the generators' stabilizers to the correlation surfaces.

    """
    if not stabilizers_to_surfaces:
        return {}
    # Sort the stabilizers by its corresponding correlation surface's area to
    # find the generators with the smallest area
    stabs_ordered_by_area = sorted(
        stabilizers_to_surfaces.keys(),
        key=lambda s: (stabilizers_to_surfaces[s].area, s),
    )
    # find a complete set of generators, starting from the smallest area
    generators: list[str] = stabs_ordered_by_area[:1]
    generators_stim: list[stim.PauliString] = [stim.PauliString(generators[0])]
    for stabilizer in stabs_ordered_by_area[1:]:
        pauli_string = stim.PauliString(stabilizer)
        if not _can_be_generated_by(pauli_string, generators_stim):
            generators.append(stabilizer)
            generators_stim.append(pauli_string)
        if hint_num_generators is not None and len(generators) == hint_num_generators:
            break
    return {g: stabilizers_to_surfaces[g] for g in generators}


def _can_be_generated_by(
    pauli_string: stim.PauliString,
    basis: list[stim.PauliString],
) -> bool:
    """Check if the given Pauli string can be generated by the given basis.

    The following procedure is used to check if a Pauli string can be generated by
    a given basis of stabilizers:

    1. ``stim.Tableau.from_stabilizers`` constructs a tableau, which represents
       a Clifford circuit mapping the Z Pauli on the nth input to the nth
       stabilizer specified in the argument at the output. That means that the
       inverse tableau maps the nth stabilizer to Z on the nth output.
    2. Apply the inverse tableau to the Pauli string. If the Pauli string is a
       product of the stabilizers, it can be decomposed into them. As a result,
       after applying the tableau, the result will have `Z` operators only on
       the specific outputs. If not, the Pauli string cannot be generated by the
       given stabilizers.

    """
    if not basis:
        return False
    tableau = stim.Tableau.from_stabilizers(
        basis,
        allow_redundant=False,
        allow_underconstrained=True,
    )
    inv = tableau.inverse(unsigned=True)
    out_paulis = inv(pauli_string)
    # use `bool()` to avoid type error
    return bool(out_paulis[len(basis) :].weight == 0)
