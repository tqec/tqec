"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

from collections.abc import Iterable
from copy import copy
from fractions import Fraction
from functools import partial, reduce
from itertools import chain, pairwise, product

import stim
from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb, multiply_paulis
from pyzx.utils import FractionLike, VertexType

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.utils import is_boundary, is_hardmard, is_s, is_x_no_phase, is_z_no_phase
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
    # _check_spiders_are_supported(g)
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
        graph = {}
        graph[leaf] = {}
        graph[leaf][neighbor] = basis
        graph[neighbor] = {}
        graph[neighbor][leaf] = _flip_pauli_based_on_edge_type(g, (leaf, neighbor), basis)
        pauli_graphs.append(graph)

    if g.vertex_degree(neighbor) == 1:  # make sure no leaf node will be in the frontier
        frontier = []
        if neighbor in bases_at_leaves:
            pauli_graphs = list(
                filter(
                    lambda pg: pg[neighbor][leaf] in (bases_at_leaves[neighbor], Pauli.I),
                    pauli_graphs,
                )
            )
    else:
        frontier = [neighbor]
        explored_leaves = [leaf]

    while frontier:
        stabilizer_nodes = explored_leaves + frontier
        stabilizer_length = sum(len(pauli_graphs[0][n]) for n in stabilizer_nodes)
        current_node = frontier.pop(0)
        unconnected_neighbors = list(
            filter(
                lambda n: n not in pauli_graphs[0][current_node],
                g.neighbors(current_node),
            )
        )
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in pauli_graphs[0]]
        flip_basis = g.type(current_node) == VertexType.X
        broadcast_basis = Basis.Z if flip_basis else Basis.X
        passthrough_basis = broadcast_basis.flipped()

        # check if each Pauli graph candidate satisfies broadcast and passthrough constraints
        # on the current node and is not a product of previously checked valid Pauli graphs
        valid_graphs, invalid_graphs, syndromes, stabilizer_list, stabilizer_basis = (
            [],
            [],
            [],
            [],
            [],
        )
        for pauli_graph in pauli_graphs:
            supports = _pauli_support_on_nodes(pauli_graph, [current_node])
            passthrough_parity = sum(supports[1 - flip_basis]) % 2
            valid = True
            syndrome = supports[flip_basis]
            if all(syndrome):
                broadcast_pauli = Pauli[broadcast_basis.value]
            elif not any(syndrome):
                broadcast_pauli = Pauli.I
            else:  # invalid broadcast
                valid = False
            if not unconnected_neighbors:
                syndrome += [passthrough_parity]
                if passthrough_parity:  # invalid passthrough
                    valid = False

            stabilizer = _bits_to_int(
                chain.from_iterable(_pauli_support_on_nodes(pauli_graph, stabilizer_nodes))
            )
            # if _find_subset_xor(stabilizer, stabilizer_list) is not None:
            #     continue
            if _in_basis(stabilizer, stabilizer_basis):
                continue
            if valid:
                if stabilizer:
                    stabilizer_basis = _build_basis(stabilizer_basis, stabilizer)
                    stabilizer_list.append(stabilizer)
                valid_graphs.append((pauli_graph, broadcast_pauli, passthrough_parity))
                if len(stabilizer_list) == stabilizer_length:
                    break
            else:
                invalid_graphs.append(pauli_graph)
                syndromes.append(sum(b << i for i, b in enumerate(syndrome)))

        # try to fix local constraint violations by multiplying with other invalid graphs
        all_one = (1 << len(syndrome)) - 1
        if not unconnected_neighbors:
            all_one ^= 1 << (len(syndrome) - 1)
        for i, (pauli_graph, syndrome) in enumerate(zip(invalid_graphs, syndromes)):
            if len(stabilizer_list) == stabilizer_length:
                break
            for target in (syndrome, syndrome ^ all_one):
                indices = _find_subset_xor(target, syndromes[:i] + syndromes[i + 1 :])
                if indices is None:
                    continue
                indices = [j if j < i else j + 1 for j in indices]
                new_pauli_graph = reduce(
                    _multiply_pauli_graphs,
                    [pauli_graph] + [invalid_graphs[j] for j in indices],
                )

                supports = _pauli_support_on_nodes(new_pauli_graph, [current_node])
                passthrough_parity = sum(supports[1 - flip_basis]) % 2
                if all(supports[flip_basis]):
                    broadcast_pauli = Pauli[broadcast_basis.value]
                else:
                    broadcast_pauli = Pauli.I

                stabilizer = _bits_to_int(
                    chain.from_iterable(_pauli_support_on_nodes(new_pauli_graph, stabilizer_nodes))
                )
                # if _find_subset_xor(stabilizer, stabilizer_list) is not None:
                #     continue
                if _in_basis(stabilizer, stabilizer_basis):
                    continue
                if stabilizer:
                    stabilizer_basis = _build_basis(stabilizer_basis, stabilizer)
                    stabilizer_list.append(stabilizer)
                valid_graphs.append((new_pauli_graph, broadcast_pauli, passthrough_parity))
                break

        # enumerate new branches
        pauli_graphs = []
        for pauli_graph, broadcast_pauli, passthrough_parity in valid_graphs:
            combined_pauli = broadcast_pauli * Pauli[passthrough_basis.value]
            if passthrough_parity:
                out_paulis_list = [
                    {
                        n: combined_pauli if n == m else broadcast_pauli
                        for n in unconnected_neighbors
                    }
                    for m in unconnected_neighbors
                ] or [{}]
            else:
                out_paulis_list = [
                    {
                        n: combined_pauli if n in m else broadcast_pauli
                        for n in unconnected_neighbors
                    }
                    for m in pairwise(unconnected_neighbors)
                ] + [{n: broadcast_pauli for n in unconnected_neighbors}]

            for out_paulis in out_paulis_list:
                new_pauli_graph = copy(pauli_graph)
                new_pauli_graph[current_node] = copy(pauli_graph[current_node])
                for n, pauli in out_paulis.items():
                    if n not in new_pauli_graph:
                        new_pauli_graph[n] = {}
                    else:
                        new_pauli_graph[n] = copy(pauli_graph[n])
                    new_pauli_graph[n][current_node] = _flip_pauli_based_on_edge_type(
                        g, (current_node, n), pauli
                    )
                    new_pauli_graph[current_node][n] = pauli
                pauli_graphs.append(new_pauli_graph)

        if not pauli_graphs:  # no valid correlation surface exists on this ZX graph
            return []
        frontier.extend(
            filter(
                lambda n: g.vertex_degree(n) > 1 and n not in pauli_graph,
                unexplored_neighbors,
            )
        )
        explored_leaves.extend(filter(lambda n: g.vertex_degree(n) == 1, unexplored_neighbors))
    return list(
        # filter(
        # lambda s: _leaf_nodes_can_support_span(g, s.span),
        map(partial(_pauli_graph_to_correlation_surface, g), pauli_graphs),
        # )
    )


def _bits_to_int(bits: Iterable[bool]) -> int:
    """Convert a list of bits to an integer."""
    return sum(b << i for i, b in enumerate(bits))


def _pauli_support_on_nodes(
    pauli_graph: dict[int, dict[int, Pauli]], nodes: list[int]
) -> tuple[list[bool], list[bool]]:
    """Get the Pauli support on the given nodes from the Pauli graph."""
    incident_paulis = list(chain.from_iterable(pauli_graph[n].values() for n in nodes))
    return [p.has_basis(Basis.X) for p in incident_paulis], [
        p.has_basis(Basis.Z) for p in incident_paulis
    ]


def _build_basis(basis: list[int], x: int) -> list[int]:
    for b in basis:
        x = min(x, x ^ b)
    if x:
        basis.append(x)
    return basis


def _in_basis(x: int, basis: list[int]) -> bool:
    for b in basis:
        x = min(x, x ^ b)
    return x == 0


def _find_subset_xor(target: int, candidates: list[int]) -> list[int] | None:
    """Given target and candidates list of ints, return list of indices i
    such that XOR of candidates[i] over indices = target,
    or None if no such subset exists.
    """  # noqa: D205
    # Build XOR basis: pivot_bit -> (basis_vector, combination_mask)
    basis = {}  # pivot_bit -> (vec, mask) where mask is int with bits for indices
    for i, vec in enumerate(candidates):
        mask = 1 << i
        v = vec
        while v:
            hb = v.bit_length() - 1  # index of highest set bit
            if hb not in basis:
                basis[hb] = (v, mask)
                break
            v ^= basis[hb][0]
            mask ^= basis[hb][1]
        # if v becomes 0, this vector was redundant; we just drop it

    # Try to express a using the same basis
    result_mask = 0
    while target:
        hb = target.bit_length() - 1
        if hb not in basis:
            return None  # cannot represent a
        target ^= basis[hb][0]
        result_mask ^= basis[hb][1]

    # Convert mask to list of indices
    return [i for i in range(len(candidates)) if (result_mask >> i) & 1]


def _multiply_pauli_graphs(
    pauli_graph_a: dict[int, dict[int, Pauli]],
    pauli_graph_b: dict[int, dict[int, Pauli]],
) -> dict[int, dict[int, Pauli]]:
    """Multiply two Pauli graphs of the same scope to form a new Pauli graph."""
    new_pauli_graph = {}
    for (v, neighbors_a), neighbors_b in zip(pauli_graph_a.items(), pauli_graph_b.values()):
        new_pauli_graph[v] = {}
        for (n, pauli_a), pauli_b in zip(neighbors_a.items(), neighbors_b.values()):
            new_pauli_graph[v][n] = pauli_a * pauli_b
    return new_pauli_graph


def _pauli_graph_to_correlation_surface(
    g: GraphS,
    pauli_graph: dict[int, dict[int, Pauli]],
) -> CorrelationSurface:
    """Convert a Pauli graph to a correlation surface."""
    span: set[ZXEdge] = set()
    for u, v in g.edges():
        pauli_u = pauli_graph[u][v]
        pauli_v = pauli_graph[v][u]
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
    return bool(out_paulis[len(basis) :].weight == 0)
