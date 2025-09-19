"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from fractions import Fraction

import stim
from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb, multiply_paulis
from pyzx.utils import FractionLike, VertexType

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.utils import (
    is_boundary,
    is_hardmard,
    is_s,
    is_x_no_phase,
    is_z_no_phase,
    is_zx_no_phase,
)
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError


def correlation_surface_to_pauli_web(
    correlation_surface: CorrelationSurface, g: GraphS
) -> PauliWeb[int, tuple[int, int]]:
    """Convert the correlation surface to a Pauli web.

    Args:
        correlation_surface: The correlation surface to convert.
        g: The ZX graph the correlation surface is based on.

    Returns:
        A `PauliWeb` representation of the correlation surface.

    """
    half_edge_bases: dict[tuple[int, int], set[str]] = {}
    for edge in correlation_surface.span:
        u, v = edge.u, edge.v
        half_edge_bases.setdefault((u.id, v.id), set()).add(u.basis.value)
        half_edge_bases.setdefault((v.id, u.id), set()).add(v.basis.value)

    pauli_web = PauliWeb(g)
    for e, bases in half_edge_bases.items():
        pauli = "I"
        for basis in bases:
            pauli = multiply_paulis(pauli, basis)
        pauli_web.add_half_edge(e, pauli)
    return pauli_web


def pauli_web_to_correlation_surface(
    pauli_web: PauliWeb[int, tuple[int, int]],
) -> CorrelationSurface:
    """Create a correlation surface from a Pauli web."""
    span: set[ZXEdge] = set()
    half_edges: dict[tuple[int, int], str] = pauli_web.half_edges()
    while half_edges:
        (u, v), pauli_u = half_edges.popitem()
        pauli_v = half_edges.pop((v, u))
        if pauli_u == "Y":  # pragma: no cover
            span.add(ZXEdge(ZXNode(u, Basis.X), ZXNode(v, Basis.Z)))
            span.add(ZXEdge(ZXNode(u, Basis.Z), ZXNode(v, Basis.Z)))
            continue
        span.add(ZXEdge(ZXNode(u, Basis(pauli_u)), ZXNode(v, Basis(pauli_v))))
    return CorrelationSurface(frozenset(span))


def find_correlation_surfaces(
    g: GraphS,
    roots: set[int] | None = None,
    reduce_to_minimal_generators: bool = True,
) -> list[CorrelationSurface]:
    """Find the correlation surfaces in a ZX graph.

    Starting from each leaf node in the graph, the function explores how can the X/Z logical
    observable move through the graph to form a correlation surface:

    - For a X/Z type leaf node, it can only support the logical observable with the opposite type.
      Only a single type of logical observable is explored from the leaf node.
    - For a Y type leaf node, it can only support the Y logical observable, i.e. the presence of
      both X and Z logical observable. Both X and Z type logical observable are explored from the
      leaf node. And the two correlation surfaces are combined to form the Y type correlation
      surface.
    - For the BOUNDARY node, it can support any type of logical observable. Both X and Z type
      logical observable are explored from it.

    The function uses a flood fill like recursive algorithm to find the correlation surface in the
    graph.
    Firstly, we define two types of nodes in the graph:

    - *broadcast node:* A node that has seen logical observable with basis opposite to its own
      basis. A logical observable needs to be broadcasted to all the neighbors of the node.
    - *passthrough node:* A node that has seen logical observable with the same basis as its own
      basis. A logical observable needs to be only supported on an even number of edges connected
      to the node.

    The algorithm starts from a set of frontier nodes and greedily expands the correlation
    surface until no more broadcast nodes are in the frontier. Then it explore the
    passthrough nodes, and select even number of edges to be included in the surface. If
    no such selection can be made, the search is pruned. For different choices, the algorithm
    recursively explores the next frontier until the search is completed. Finally, the branches
    at different nodes are produced to form the correlation surface.

    Args:
        g: The ZX graph to find the correlation surfaces.
        roots: The set of leaf nodes to start the correlation surface finding. If not provided,
            all the leaf nodes in the graph are used.
        reduce_to_minimal_generators: Whether to reduce the correlation surfaces to the minimal
            generators. Other correlation surfaces can be obtained by multiplying the generators.
            The generators are chosen to be the smallest in terms of the correlation surface area.
            Default is `True`.

    Returns:
        A list of `CorrelationSurface` in the graph.

    """
    _check_spiders_are_supported(g)
    # Edge case: single node graph
    if g.num_vertices() == 1:
        v = next(iter(g.vertices()))
        basis = Basis.X if is_z_no_phase(g, v) else Basis.Z
        node = ZXNode(v, basis)
        return [CorrelationSurface(frozenset({ZXEdge(node, node)}))]
    # Find correlation surfaces starting from each leaf node
    leaves = {v for v in g.vertices() if g.vertex_degree(v) == 1}
    if roots is not None:
        if not roots.issubset(leaves):
            raise TQECError("The roots must all be leaf nodes, i.e. degree 1 nodes.")
        leaves = roots
    if not leaves:
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )
    correlation_surfaces: set[CorrelationSurface] = set()
    for leaf in leaves:
        correlation_surfaces.update(_find_correlation_surfaces_from_leaf(g, leaf))

    if reduce_to_minimal_generators:
        stabilizers_to_surfaces = {
            surface.external_stabilizer(sorted(leaves)): surface for surface in correlation_surfaces
        }
        correlation_surfaces = set(
            reduce_observables_to_minimal_generators(stabilizers_to_surfaces).values()
        )

    # sort the correlation surfaces to make the result deterministic
    return sorted(correlation_surfaces, key=lambda x: sorted(x.span))


def _find_correlation_surfaces_from_leaf(
    g: GraphS,
    leaf: int,
) -> list[CorrelationSurface]:
    """Find the correlation surfaces starting from a leaf node in the graph."""
    spans: list[frozenset[ZXEdge]] = []
    # Z/X type node can only support the correlation surface with the opposite type.
    if is_zx_no_phase(g, leaf):
        basis = Basis.X if is_z_no_phase(g, leaf) else Basis.Z
        spans = _find_spans_with_flood_fill(g, {ZXNode(leaf, basis)}, set()) or []
    else:
        x_spans = _find_spans_with_flood_fill(g, {ZXNode(leaf, Basis.X)}, set()) or []
        z_spans = _find_spans_with_flood_fill(g, {ZXNode(leaf, Basis.Z)}, set()) or []
        # For the port node, try to construct both the x and z type correlation surfaces.
        if is_boundary(g, leaf):
            spans = x_spans + z_spans
        else:
            # For the Y type node, the correlation surface must be the product of the x and z type.
            assert is_s(g, leaf)
            spans = [sx | sz for sx, sz in itertools.product(x_spans, z_spans)]
    return [
        CorrelationSurface(span) for span in spans if span and _leaf_nodes_can_support_span(g, span)
    ]


def _leaf_nodes_can_support_span(g: GraphS, span: frozenset[ZXEdge]) -> bool:
    """Check if the leaf nodes in the graph can support the correlation span.

    The compatibility is determined by comparing the logical observable basis
    and the node type for the leaf nodes in the graph:

    - The Z/X observable must be supported on the opposite type node.
    - The Y observable can only be supported on the Y type node.
    - The BOUNDARY node can support any type of logical observable.

    """
    no_boundary_leaves = {
        v for v in g.vertices() if g.vertex_degree(v) == 1 and not is_boundary(g, v)
    }
    bases_at_leaves: dict[int, set[Basis]] = {}
    for edge in span:
        u, ub = edge.u.id, edge.u.basis
        v, vb = edge.v.id, edge.v.basis
        if u in no_boundary_leaves:
            bases_at_leaves.setdefault(u, set()).add(ub)
        if v in no_boundary_leaves:
            bases_at_leaves.setdefault(v, set()).add(vb)
    for leaf, bases in bases_at_leaves.items():
        # If there is correlation surface touching a Y leaf node, then the
        # correlation surface must support both X and Z type logical observable.
        if is_s(g, leaf):
            return bases == {Basis.X, Basis.Z}
        # Z(X) type leaf node can only support the X(Z) type logical observable.
        if is_z_no_phase(g, leaf) and bases != {Basis.X}:
            return False
        if is_x_no_phase(g, leaf) and bases != {Basis.Z}:
            return False
    return True


def _find_spans_with_flood_fill(
    g: GraphS,
    frontier: set[ZXNode],
    current_span: set[ZXEdge],
) -> list[frozenset[ZXEdge]] | None:
    """Find the correlation spans in the ZX graph using the flood fill like algorithm."""
    # The node type mismatches the logical observable basis, then we can flood
    # through(broadcast) all the edges connected to the current node.
    # Greedily flood through the edges until encountering the passthrough node.
    broadcast_nodes = {nb for nb in frontier if _can_broadcast(g, nb)}
    while broadcast_nodes:
        cur = broadcast_nodes.pop()
        frontier.remove(cur)
        for neighbor in _iter_neighbor_nodes(g, cur):
            edge = ZXEdge(cur, neighbor)
            if edge in current_span:
                continue
            frontier.add(neighbor)
            current_span.add(edge)
            if _can_broadcast(g, neighbor):
                broadcast_nodes.add(neighbor)

    if not frontier:
        return [frozenset(current_span)]

    # The node type matches the observable basis, enforce the parity to be even.
    # There are different choices of the edges to be included in the span.

    # Each list entry represents the possible branches at a node.
    # Each tuple in the list entry represents a branch, where the first element is the
    # nodes to be included in the branch's frontier, and the second element is the edges
    # to be included in the branch's span.
    branches_at_different_nodes: list[list[tuple[set[ZXNode], set[ZXEdge]]]] = []
    for cur in set(frontier):
        assert not _can_broadcast(g, cur)
        frontier.remove(cur)

        edges = {ZXEdge(cur, neighbor) for neighbor in _iter_neighbor_nodes(g, cur)}
        edges_in_span = edges & current_span
        edges_left = edges - current_span
        parity = len(edges_in_span) % 2
        # Cannot fulfill the parity requirement, prune the search
        if parity == 1 and not edges_left:
            return None
        # starts from a node that only has a single edge
        if parity == 0 and not edges_in_span and len(edges_left) <= 1:
            return None
        branches_at_node: list[tuple[set[ZXNode], set[ZXEdge]]] = []
        for n in range(parity, len(edges_left) + 1, 2):
            branches_at_node.extend(
                (
                    {e.u if e.u != cur else e.v for e in branch_edges},
                    set(branch_edges),
                )
                for branch_edges in itertools.combinations(edges_left, n)
            )
        branches_at_different_nodes.append(branches_at_node)

    assert branches_at_different_nodes, "Should not be empty."

    final_spans: list[frozenset[ZXEdge]] = []
    # Product of the branches at different nodes together
    for product in itertools.product(*branches_at_different_nodes):
        product_frontier = set(frontier)
        product_span = set(current_span)
        for nodes, edges in product:
            product_frontier.update(nodes)
            product_span.update(edges)
        spans = _find_spans_with_flood_fill(g, product_frontier, product_span)
        if spans is not None:
            final_spans.extend(spans)

    return final_spans or None


def _iter_neighbor_nodes(g: GraphS, n: ZXNode) -> Iterator[ZXNode]:
    for edge in g.incident_edges(n.id):
        neighbor = edge[1] if edge[0] == n.id else edge[0]
        neighbor_basis = n.basis.flipped() if is_hardmard(g, edge) else n.basis
        yield ZXNode(neighbor, neighbor_basis)


def _can_broadcast(g: GraphS, n: ZXNode) -> bool:
    if not is_zx_no_phase(g, n.id):
        return True
    vt = g.type(n.id)
    if n.basis == Basis.X:
        return vt is VertexType.Z
    return vt is VertexType.X


_SUPPORTED_SPIDERS: set[tuple[VertexType, FractionLike]] = {
    (VertexType.Z, 0),  # Z
    (VertexType.X, 0),  # X
    (VertexType.Z, Fraction(1, 2)),  # S
    (VertexType.BOUNDARY, 0),  # Boundary
}


def _check_spiders_are_supported(g: GraphS) -> None:
    """Check the preconditions for the correlation surface finding algorithm."""
    # 1. Check the spider types and phases are supported
    for v in g.vertices():
        vt = g.type(v)
        phase = g.phase(v)
        if (vt, phase) not in _SUPPORTED_SPIDERS:
            raise TQECError(f"Unsupported spider type and phase: {vt} and {phase}.")
    # 2. Check degree of the spiders
    for v in g.vertices():
        degree = g.vertex_degree(v)
        if is_boundary(g, v) and degree != 1:
            raise TQECError(f"Boundary spider must be dangling, but got {degree} neighbors.")
        if is_s(g, v) and degree != 1:
            raise TQECError(f"S spider must be dangling, but got {degree} neighbors.")


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
        key=lambda s: (stabilizers_to_surfaces[s].area(), s),
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
    tableau = stim.Tableau.from_stabilizers(
        basis,
        allow_redundant=False,
        allow_underconstrained=True,
    )
    inv = tableau.inverse(unsigned=True)
    out_paulis = inv(pauli_string)
    # use `bool()` to avoid type error
    return bool(out_paulis[len(basis) :].weight == 0)
