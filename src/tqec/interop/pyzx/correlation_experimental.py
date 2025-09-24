"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

from fractions import Fraction
from functools import partial, reduce
from itertools import chain, combinations, product

import networkx as nx
import numpy as np
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
)
from tqec.utils.enums import Basis, Pauli
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
        pauli = reduce(multiply_paulis, bases, "I")
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
    g: GraphS, reduce_to_minimal_generators: bool = True
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

    Args:
        g: The ZX graph to find the correlation surfaces.
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
    if not leaves:
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )
    correlation_surfaces = _find_correlation_surfaces_from_leaf(g, next(iter(leaves)))

    if CorrelationSurface(frozenset()) in correlation_surfaces:
        correlation_surfaces.remove(CorrelationSurface(frozenset()))

    if reduce_to_minimal_generators:
        stabilizers_to_surfaces = {
            surface.external_stabilizer(sorted(leaves)): surface for surface in correlation_surfaces
        }
        stabilizers_to_surfaces.pop("I" * len(leaves), None)
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
    bases_at_leaves: dict[int, Pauli] = {}
    for closed_leaf in filter(
        lambda v: g.vertex_degree(v) == 1 and not is_boundary(g, v), g.vertices()
    ):
        if is_s(g, closed_leaf):
            bases_at_leaves[closed_leaf] = Pauli.Y
        elif is_z_no_phase(g, closed_leaf):
            bases_at_leaves[closed_leaf] = Pauli.X
        else:
            bases_at_leaves[closed_leaf] = Pauli.Z
    neighbor = next(iter(g.neighbors(leaf)))
    pauli_graphs = []
    for basis in (
        [bases_at_leaves[leaf]] if leaf in bases_at_leaves else [Pauli.X, Pauli.Z, Pauli.Y]
    ) + [Pauli.I]:
        graph = nx.Graph()
        graph.add_node(leaf)
        graph.nodes[leaf][neighbor] = basis
        graph.add_node(neighbor)
        graph.nodes[neighbor][leaf] = _flip_pauli_based_on_edge_type(g, (leaf, neighbor), basis)
        graph.add_edge(leaf, neighbor)
        pauli_graphs.append(graph)
    if g.vertex_degree(neighbor) == 1:  # make sure no leaf node will be in the frontier
        frontier = []
        if neighbor in bases_at_leaves:
            pauli_graphs = list(
                filter(
                    lambda pg: pg.nodes[neighbor][leaf] in (bases_at_leaves[neighbor], Pauli.I),
                    pauli_graphs,
                )
            )
    else:
        frontier = [neighbor]
        explored_leaves = [leaf]

    while frontier:
        stabilizer_nodes = explored_leaves + frontier
        cur = frontier.pop()
        unconnected_neighbors = sorted(
            filter(lambda n: n not in pauli_graphs[0][cur], g.neighbors(cur))
        )
        # neighbor_leaves_bases = {
        #     n: _flip_pauli_based_on_edge_type(g, (cur, n), bases_at_leaves[n])
        #     for n in unconnected_neighbors
        #     if n in bases_at_leaves
        # }
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in pauli_graphs[0]]
        broadcast_basis = "X" if g.type(cur) == VertexType.Z else "Z"
        passthrough_basis = Basis[broadcast_basis].flipped()

        valid_graphs, invalid_graphs, syndromes = [], [], []
        stabilizer_list = []
        for pauli_graph in pauli_graphs:
            incident_paulis = pauli_graph.nodes[cur].values()
            passthrough_parity = sum(p.has_basis(passthrough_basis) for p in incident_paulis) % 2
            broadcast_supports = [p.has_basis(broadcast_basis) for p in incident_paulis]
            valid = True
            if all(broadcast_supports):
                broadcast_pauli = Pauli[broadcast_basis]
            elif not any(broadcast_supports):
                broadcast_pauli = Pauli.I
            else:  # invalid broadcast
                valid = False
            if not unconnected_neighbors and passthrough_parity:  # invalid passthrough
                valid = False
                broadcast_supports += [True]

            stabilizer = stim.PauliString(
                "".join(
                    pauli.value
                    for pauli in chain.from_iterable(
                        pauli_graph.nodes[n].values() for n in stabilizer_nodes
                    )
                )
            )
            if _can_be_generated_by(stabilizer, stabilizer_list):
                continue
            if valid:
                if stabilizer != stim.PauliString("I" * len(stabilizer)):
                    stabilizer_list.append(stabilizer)
                valid_graphs.append((pauli_graph, broadcast_pauli, passthrough_parity))
                if len(stabilizer_list) == 2 * len(stabilizer_nodes):
                    break
            else:
                invalid_graphs.append(pauli_graph)
                syndromes.append(
                    np.array(broadcast_supports).dot(1 << np.arange(len(broadcast_supports)))
                )

        for i, (pauli_graph, syndrome) in enumerate(zip(invalid_graphs, syndromes)):
            if len(stabilizer_list) == 2 * len(stabilizer_nodes):
                break
            for indices in chain.from_iterable(
                combinations(range(len(invalid_graphs)), num_flips)
                for num_flips in range(1, len(invalid_graphs) + 1)
            ):
                if i in indices:
                    continue
                new_pauli_graph = reduce(
                    _multiply_pauli_graphs, [invalid_graphs[j] for j in indices]
                )

                incident_paulis = new_pauli_graph.nodes[cur].values()
                passthrough_parity = (
                    sum(p.has_basis(passthrough_basis) for p in incident_paulis) % 2
                )
                broadcast_supports = [p.has_basis(broadcast_basis) for p in incident_paulis]
                valid = True
                if all(broadcast_supports):
                    broadcast_pauli = Pauli[broadcast_basis]
                elif not any(broadcast_supports):
                    broadcast_pauli = Pauli.I
                else:  # invalid broadcast
                    continue
                if not unconnected_neighbors and passthrough_parity:  # invalid passthrough
                    continue

                stabilizer = stim.PauliString(
                    "".join(
                        pauli.value
                        for pauli in chain.from_iterable(
                            new_pauli_graph.nodes[n].values() for n in stabilizer_nodes
                        )
                    )
                )
                if _can_be_generated_by(stabilizer, stabilizer_list):
                    continue
                if stabilizer != stim.PauliString("I" * len(stabilizer)):
                    stabilizer_list.append(stabilizer)
                valid_graphs.append((new_pauli_graph, broadcast_pauli, passthrough_parity))
                break

        new_pauli_graphs = []
        for pauli_graph, broadcast_pauli, passthrough_parity in valid_graphs:
            passthrough_nodes_list = list(
                chain.from_iterable(
                    combinations(unconnected_neighbors, num_passthrough)
                    for num_passthrough in range(
                        passthrough_parity,
                        len(unconnected_neighbors) + 1,
                        2,
                    )
                )
            )
            out_paulis_list = [
                {
                    n: (
                        broadcast_pauli * Pauli[passthrough_basis.value]
                        if n in passthrough_nodes
                        else broadcast_pauli
                    )
                    for n in unconnected_neighbors
                }
                for passthrough_nodes in passthrough_nodes_list
            ]

            for out_paulis in out_paulis_list:
                # if any(
                #     out_paulis[n] not in (pauli, Pauli.I)
                #     for n, pauli in neighbor_leaves_bases.items()
                # ):
                #     continue
                new_pauli_graph = pauli_graph.copy()
                for n, pauli in out_paulis.items():
                    if n not in new_pauli_graph:
                        new_pauli_graph.add_node(n)
                    new_pauli_graph.nodes[n][cur] = _flip_pauli_based_on_edge_type(
                        g, (cur, n), pauli
                    )
                    new_pauli_graph.add_edge(cur, n)
                    new_pauli_graph.nodes[cur][n] = pauli
                new_pauli_graphs.append(new_pauli_graph)

        pauli_graphs = new_pauli_graphs
        if not pauli_graphs:  # there is no valid correlation surface on this ZX graph
            return []
        frontier.extend(
            filter(
                lambda n: g.vertex_degree(n) > 1 and n not in pauli_graph,
                unexplored_neighbors,
            )
        )
        explored_leaves.extend(filter(lambda n: g.vertex_degree(n) == 1, unexplored_neighbors))

    correlation_surfaces = list(map(partial(_pauli_graph_to_correlation_surface, g), pauli_graphs))
    return list(filter(lambda s: _leaf_nodes_can_support_span(g, s.span), correlation_surfaces))


def _multiply_pauli_graphs(
    pauli_graph_a: nx.Graph,
    pauli_graph_b: nx.Graph,
) -> nx.Graph:
    """Multiply two Pauli graphs of the same scope to form a new Pauli graph."""
    new_pauli_graph = pauli_graph_a.copy()
    for v in new_pauli_graph:
        for n in new_pauli_graph.neighbors(v):
            new_pauli_graph.nodes[v][n] *= pauli_graph_b.nodes[v][n]
    return new_pauli_graph


def _pauli_graph_to_correlation_surface(
    g: GraphS,
    pauli_graph: nx.Graph,
) -> CorrelationSurface:
    """Convert a Pauli graph to a correlation surface."""
    span: set[ZXEdge] = set()
    for u, v in pauli_graph.edges():
        pauli_u = pauli_graph.nodes[u][v]
        pauli_v = pauli_graph.nodes[v][u]
        for basis_u, basis_v in product(Basis, repeat=2):
            if (
                (is_hardmard(g, (u, v)) ^ (basis_u == basis_v))
                and pauli_u.has_basis(basis_u)
                and pauli_v.has_basis(basis_v)
            ):
                span.add(ZXEdge(ZXNode(u, basis_u), ZXNode(v, basis_v)))
    return CorrelationSurface(frozenset(span))


def _flip_pauli_based_on_edge_type(g: GraphS, edge: tuple[int, int], pauli: Pauli) -> Pauli:
    """Flip the Pauli operator based on the edge type."""
    return pauli.flipped() if is_hardmard(g, edge) else pauli


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
    return bool(
        out_paulis[len(basis) :].weight == 0
        and all(xy not in str(out_paulis[: len(basis)]) for xy in "XY")
    )
