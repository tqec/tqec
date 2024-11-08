"""Defines the :py:class:`~tqec.computation.correlation.CorrelationSurface` and
the functions to find the correlation surfaces in the ZX graph."""

from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Iterable

from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode, ZXEdge
from tqec.exceptions import TQECException
from tqec.position import Position3D


@dataclass(frozen=True)
class CorrelationSurface:
    """A correlation surface in the logical computation.

    The correlation surface specifies the correlation between the logical operators in the
    spacetime diagram. Logical observable can be derived from the boundaries of the correlation
    surface.

    The correlation surface is defined by the set of edges in the ZX graph. Each edge represents
    a X/Z surface within the pipe in the `BlockGraph` picture. A Y surface is represented by two
    distinct edges, one for the X surface and one for the Z surface. Therefore, the nodes of the
    edges in the correlation surface must be Z/X type nodes.


    Attributes:
        nodes: A set of ``ZXNode`` representing the nodes in the correlation surface. The kind of
            the node is determined by what kinds of correlation the node supports. If both X and
            Z correlation are supported, the node is a Y type node.
        span: A set of ``ZXEdge`` representing the correlation between logical operators spanning
            in the 3D space. The edges in the span must be between Z/X type nodes.
        external_stabilizer: A mapping from the port label to the Pauli operator at the port, which
            represents the spacetime stabilizer for the correlation surface. Sign of the stabilizer
            is neglected.
    """

    nodes: frozenset[ZXNode]
    span: frozenset[ZXEdge] = frozenset()
    external_stabilizer: dict[str, str] = field(
        default_factory=dict, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        if len(self.nodes) == 0:
            raise TQECException(
                "The correlation surface must contain at least one node."
            )
        if any(not node.is_zx_node for edge in self.span for node in edge):
            raise TQECException(
                "The edges in the correlation surface must be between Z/X type nodes.",
            )

    @staticmethod
    def from_span(zx_graph: ZXGraph, span: Iterable[ZXEdge]) -> CorrelationSurface:
        """Construct a correlation surface from the correlation span."""
        span = frozenset(span)

        correlation_types = CorrelationSurface.get_correlation_types(span)
        nodes = frozenset(ZXNode(pos, kind) for pos, kind in correlation_types.items())

        external_stabilizer = {}
        for label, port in zx_graph.ports.items():
            correlation_type = correlation_types.get(port)
            if correlation_type is None:
                external_stabilizer[label] = "I"
            else:
                external_stabilizer[label] = correlation_type.value
        return CorrelationSurface(nodes, span, external_stabilizer)

    @staticmethod
    def get_correlation_types(span: Iterable[ZXEdge]) -> dict[Position3D, ZXKind]:
        """Get the correlation types at the nodes in the correlation span.

        The correlation type at the node is determined by the
        correlation types of the edges connected to the node. If the
        node is connected to both X and Z type edges, the correlation is
        Y type. If the node is connected to only one type of edge, the
        correlation is Z/X type.
        """
        correlations_at_position: dict[Position3D, set[ZXKind]] = {}
        for edge in span:
            for node in edge:
                correlations_at_position.setdefault(node.position, set()).add(node.kind)

        correlation_types: dict[Position3D, ZXKind] = {}
        for pos, types in correlations_at_position.items():
            if len(types) == 1:
                correlation_types[pos] = types.pop()
            else:
                assert len(types) == 2
                correlation_types[pos] = ZXKind.Y
        return correlation_types

    @property
    def node_correlation_types(self) -> dict[Position3D, ZXKind]:
        """Return a mapping from the position of the node to the correlation
        type supported at the node."""
        return {node.position: node.kind for node in self.nodes}

    @property
    def has_single_node(self) -> bool:
        """Return True if the correlation surface contains only one node."""
        return len(self.nodes) == 1


def find_correlation_surfaces(
    zx_graph: ZXGraph,
) -> list[CorrelationSurface]:
    """Find all the
    :py:class:`~tqec.computation.correlation.CorrelationSurface` in a ZX graph.

    It starts from each leaf node in the graph, and finds the correlation surfaces using a variant
    of flood-fill algorithm.

    For Z/X type correlation surface, the correlation surface must start from the opposite type node. For the
    Port, the correlation surface can start from both X/Z type node. For the Y type node, the
    correlation surface must be the product of the X and Z type.

    Args:
        zx_graph: The ZX graph to find the correlation surfaces.

    Returns:
        A list of `CorrelationSurface` in the graph.
    """
    zx_graph.check_invariants()
    # Edge case: single node graph
    if zx_graph.num_nodes == 1:
        return [
            CorrelationSurface(nodes=frozenset({zx_graph.nodes[0].with_zx_flipped()}))
        ]
    # Find correlation surfaces starting from each leaf node
    leaves = set(zx_graph.leaf_nodes)
    if not leaves:
        raise TQECException(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )
    correlation_surfaces: set[CorrelationSurface] = set()
    for leaf in leaves:
        correlation_surfaces.update(find_correlation_surfaces_from_leaf(zx_graph, leaf))
    # sort the correlation surfaces to make the result deterministic
    return sorted(correlation_surfaces, key=lambda x: sorted(x.span))


def find_correlation_surfaces_from_leaf(
    zx_graph: ZXGraph,
    leaf: ZXNode,
) -> list[CorrelationSurface]:
    """Find the correlation surfaces starting from a leaf node in the ZX
    graph."""
    # Z/X type node can only support the correlation surface with the opposite type.
    if leaf.is_zx_node:
        spans = (
            _find_spans_with_flood_fill(zx_graph, {leaf.with_zx_flipped()}, set()) or []
        )
        return _construct_compatible_correlation_surfaces(zx_graph, spans)
    x_spans = (
        _find_spans_with_flood_fill(zx_graph, {ZXNode(leaf.position, ZXKind.X)}, set())
        or []
    )
    z_spans = (
        _find_spans_with_flood_fill(zx_graph, {ZXNode(leaf.position, ZXKind.Z)}, set())
        or []
    )
    # For the port node, try to construct both the x and z type correlation surfaces.
    if leaf.is_port:
        return _construct_compatible_correlation_surfaces(zx_graph, x_spans + z_spans)
    # For the Y type node, the correlation surface must be the product of the x and z type.
    assert leaf.is_y_node
    return _construct_compatible_correlation_surfaces(
        zx_graph, [sx | sz for sx, sz in itertools.product(x_spans, z_spans)]
    )


def _construct_compatible_correlation_surfaces(
    zx_graph: ZXGraph,
    spans: Iterable[frozenset[ZXEdge]],
) -> list[CorrelationSurface]:
    """From the correlation spans, construct the correlation surfaces that are
    compatible with the ZX graph.

    The compatibility is determined by comparing the correlation type
    and the node type of the leaf nodes in the graph. If the node type
    is not P, the correlation type must be the same as the node type. If
    the node type is P, the correlation type can be any type.
    """
    correlation_surfaces = []

    def _is_compatible(
        correlation_types: dict[Position3D, ZXKind],
    ) -> bool:
        # Check the leaf nodes compatibility.
        for leaf in zx_graph.leaf_nodes:
            # Port is compatible with any correlation type.
            if leaf.is_port:
                continue
            correlation_type = correlation_types.get(leaf.position)
            if correlation_type is None:
                continue
            # Y correlation can only be supported on the Y type node.
            if (correlation_type == ZXKind.Y) ^ (leaf.kind == ZXKind.Y):
                return False
            # Z/X correlation must be supported on the opposite type node.
            if correlation_type != ZXKind.Y and correlation_type == leaf.kind:
                return False
        return True

    for span in spans:
        if not span:
            continue
        correlation_surface = CorrelationSurface.from_span(zx_graph, span)
        if not _is_compatible(correlation_surface.node_correlation_types):
            continue
        correlation_surfaces.append(correlation_surface)
    return correlation_surfaces


def _find_spans_with_flood_fill(
    zx_graph: ZXGraph,
    correlation_frontier: set[ZXNode],
    correlation_span: set[ZXEdge],
) -> list[frozenset[ZXEdge]] | None:
    """Find the correlation spans in the ZX graph using the flood fill like
    algorithm.

    matched correlation node: Node at which the correlation type matches the node type.
    mismatched correlation node: Node at which the correlation type mismatches the node type.

    The algorithm starts from a set of correlation frontier and greedily expands the correlation
    span until no more mismatched correlation nodes are in the frontier. Then it explore the
    matched correlation nodes, and select even number of edges to be included in the span. If
    no such selection can be made, the search is pruned. For different choices, the algorithm
    recursively explores the next frontier until the search is completed. Finally, the branches
    at different nodes are produced to form the correlation spans.

    Args:
        zx_graph: The ZX graph to find the correlation spans in.
        correlation_frontier: The set of correlation nodes to be explored at this step.
        correlation_span: The current correlation span.

    Returns:
        A list of correlation spans, or None if no correlation spans can be found.
    """
    # The ZX node type mismatches the correlation type, then we can flood
    # through all the edges connected to the current node.
    # Greedily flood through the edges until encountering the matched correlation type.
    mismatched_correlation_nodes = {
        n for n in correlation_frontier if not _match_at(zx_graph, n)
    }
    while mismatched_correlation_nodes:
        correlation_node = mismatched_correlation_nodes.pop()
        correlation_frontier.remove(correlation_node)
        for correlation_edge in _get_correlation_edges_at(zx_graph, correlation_node):
            if correlation_edge in correlation_span:
                continue
            u, v = correlation_edge
            next_correlation_node = u if v == correlation_node else v
            correlation_frontier.add(next_correlation_node)
            correlation_span.add(correlation_edge)
            if not _match_at(zx_graph, next_correlation_node):
                mismatched_correlation_nodes.add(next_correlation_node)

    if not correlation_frontier:
        return [frozenset(correlation_span)]

    # The node type matches the correlation type, enforce the parity to be even.
    # There are different choices of the edges to be included in the span.

    # Each list entry represents the possible branches at a node.
    # Each tuple in the list entry represents a branch, where the first element is the
    # nodes to be included in the branch's frontier, and the second element is the edges
    # to be included in the branch's span.
    branches_at_different_nodes: list[list[tuple[set[ZXNode], set[ZXEdge]]]] = []
    for correlation_node in set(correlation_frontier):
        assert _match_at(zx_graph, correlation_node)
        correlation_frontier.remove(correlation_node)

        correlation_edges = _get_correlation_edges_at(zx_graph, correlation_node)
        edges_in_span = correlation_edges & correlation_span
        edges_left = correlation_edges - correlation_span
        parity = len(edges_in_span) % 2
        # Cannot fulfill the parity requirement, prune the search
        if parity == 1 and not edges_left:
            return None
        # starts from a node that only has a single edge
        if parity == 0 and not edges_in_span and len(edges_left) <= 1:
            return None
        branches_at_node: list[tuple[set[ZXNode], set[ZXEdge]]] = []
        for n in range(parity, len(edges_left) + 1, 2):
            for branch_edges in itertools.combinations(edges_left, n):
                branches_at_node.append(
                    (
                        {e.u if e.u != correlation_node else e.v for e in branch_edges},
                        set(branch_edges),
                    )
                )
        branches_at_different_nodes.append(branches_at_node)

    assert branches_at_different_nodes, "Should not be empty."

    final_spans: list[frozenset[ZXEdge]] = []
    # Product of the branches at different nodes together
    for product in itertools.product(*branches_at_different_nodes):
        product_frontier = set(correlation_frontier)
        product_span = set(correlation_span)
        for nodes, edges in product:
            product_frontier.update(nodes)
            product_span.update(edges)
        spans = _find_spans_with_flood_fill(zx_graph, product_frontier, product_span)
        if spans is not None:
            final_spans.extend(spans)
    return final_spans or None


def _get_correlation_edges_at(
    zx_graph: ZXGraph,
    correlation_node: ZXNode,
) -> set[ZXEdge]:
    correlation_edges: set[ZXEdge] = set()
    zx_node = zx_graph[correlation_node.position]
    for zx_edge in set(zx_graph.edges_at(correlation_node.position)):
        next_zx_node = zx_edge.u if zx_edge.v == zx_node else zx_edge.v
        next_correlation_kind = (
            correlation_node.kind.with_zx_flipped()
            if zx_edge.has_hadamard
            else correlation_node.kind
        )
        next_correlation_node = ZXNode(next_zx_node.position, next_correlation_kind)
        correlation_edges.add(
            ZXEdge(correlation_node, next_correlation_node, zx_edge.has_hadamard)
        )
    return correlation_edges


def _match_at(zx_graph: ZXGraph, correlation_node: ZXNode) -> bool:
    zx_node = zx_graph[correlation_node.position]
    return zx_node.kind == correlation_node.kind
