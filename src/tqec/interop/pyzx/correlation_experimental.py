"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

import operator
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

    # sort the correlation surfaces to make the result deterministic
    return sorted(correlation_surfaces, key=lambda x: sorted(x.span))


class PauliGraph(dict[int, dict[int, tuple[bool, bool]]]):
    """Correlation surface represented as X and Z supports on half-edges."""

    def add_support(
        self, zx_graph: GraphS, edge: tuple[int, int], xz_support: tuple[bool, bool]
    ) -> PauliGraph:
        """Add X and Z supports on the edge (u, v)."""
        for (u, v), support in zip(
            (edge, edge[::-1]),
            (
                xz_support,
                xz_support[::-1] if is_hardmard(zx_graph, edge) else xz_support,
            ),
        ):
            if u not in self:
                self[u] = {}
            self[u][v] = support
        return self

    def support_on_nodes(
        self, nodes: list[int], transpose: bool = True
    ) -> tuple[tuple[bool], tuple[bool]] | tuple[tuple[bool, bool]]:
        """Get the X and Z supports on the given nodes."""
        supports = chain.from_iterable(self[n].values() for n in nodes)
        return tuple(zip(*supports)) if transpose else tuple(supports)

    def to_correlation_surface(self, zx_graph: GraphS) -> CorrelationSurface:
        """Convert a Pauli graph to a correlation surface."""
        span = []
        bases = (Basis.X, Basis.Z)
        for u, v in zx_graph.edges():
            pauli_u = self[u][v]
            pauli_v = self[v][u]
            for basis_u, basis_v in product(range(2), repeat=2):
                if (
                    (is_hardmard(zx_graph, (u, v)) ^ (basis_u == basis_v))
                    and pauli_u[basis_u]
                    and pauli_v[basis_v]
                ):
                    span.append(ZXEdge(ZXNode(u, bases[basis_u]), ZXNode(v, bases[basis_v])))
        return CorrelationSurface(frozenset(span))


def _multiply_pauli_graphs(pauli_graphs: list[PauliGraph]) -> PauliGraph:
    new_pauli_graph = PauliGraph()
    for v, neighbors in zip(pauli_graphs[0], zip(*(pg.values() for pg in pauli_graphs))):
        new_pauli_graph[v] = {}
        for n, supports in zip(neighbors[0], zip(*(neighbor.values() for neighbor in neighbors))):
            new_pauli_graph[v][n] = tuple(reduce(partial(map, operator.xor), supports))
    return new_pauli_graph


def _find_correlation_surfaces_from_leaf(zx_graph: GraphS, leaf: int) -> list[CorrelationSurface]:
    x_leaves, y_leaves, z_leaves = [], [], []
    for closed_leaf in filter(
        lambda v: zx_graph.vertex_degree(v) == 1 and not is_boundary(zx_graph, v),
        zx_graph.vertices(),
    ):
        if is_s(zx_graph, closed_leaf):
            y_leaves.append(closed_leaf)
        elif is_z_no_phase(zx_graph, closed_leaf):
            z_leaves.append(closed_leaf)
        else:
            x_leaves.append(closed_leaf)
    pauli_graphs = _find_pauli_graph_generator_set_from_leaf(zx_graph, leaf)
    if sum(len(leaves) for leaves in (x_leaves, y_leaves, z_leaves)) == 0:
        basis_pauli_graphs = pauli_graphs
    stabilizer_basis, basis_pauli_graphs, valid_pauli_graphs = {}, [], []
    for pauli_graph in pauli_graphs:
        stabilizer = _bits_to_int(
            chain.from_iterable(
                map(func, pauli_graph.support_on_nodes(leaves, transpose=False))
                for leaves, func in zip(
                    (x_leaves, y_leaves, z_leaves),
                    (lambda a: a[0], lambda a: a[0] ^ a[1], lambda a: a[1]),
                )
            )
        )
        indices = _solve_linear_system(stabilizer_basis, stabilizer, update_basis=True)
        if indices is None:
            basis_pauli_graphs.append(pauli_graph)
            continue
        valid_pauli_graphs.append(
            _multiply_pauli_graphs([basis_pauli_graphs[k] for k in indices] + [pauli_graph])
        )
    return [pg.to_correlation_surface(zx_graph) for pg in valid_pauli_graphs]


def _find_pauli_graph_generator_set_from_leaf(zx_graph: GraphS, leaf: int) -> list[PauliGraph]:
    """Find the correlation surfaces starting from a leaf node in the graph."""
    neighbor: int = next(iter(zx_graph.neighbors(leaf)))
    pauli_graphs: list[PauliGraph] = [
        PauliGraph().add_support(zx_graph, (leaf, neighbor), support)
        for support in [(True, False), (False, True)]
    ]

    frontier: list[int] = []
    if zx_graph.vertex_degree(neighbor) != 1:  # make sure no leaf node will be in the frontier
        frontier.append(neighbor)
        explored_leaves = [leaf]
        explored_nodes = {leaf}

    while frontier:
        stabilizer_nodes = explored_leaves + frontier
        stabilizer_length = sum(len(pauli_graphs[0][n]) for n in stabilizer_nodes)
        current_node = frontier.pop(0)
        unconnected_neighbors: list[int] = list(
            filter(
                lambda n: n not in pauli_graphs[0][current_node],
                zx_graph.neighbors(current_node),
            )
        )
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in pauli_graphs[0]]
        is_x_node: bool = zx_graph.type(current_node) == VertexType.X
        broadcast_basis = (False, True) if is_x_node else (True, False)
        passthrough_basis = broadcast_basis[::-1]

        # check if each Pauli graph candidate satisfies broadcast and passthrough constraints
        # on the current node and is not a product of previously checked valid Pauli graphs
        valid_graphs, invalid_graphs, syndromes, stabilizer_basis = [], [], [], {}
        for pauli_graph in pauli_graphs:
            supports: tuple[tuple[bool], tuple[bool]] = pauli_graph.support_on_nodes([current_node])
            passthrough_parity = sum(supports[1 - is_x_node]) % 2
            valid = True
            syndrome: tuple[bool] = supports[is_x_node]
            if all(syndrome):
                broadcast_pauli = broadcast_basis
            elif not any(syndrome):
                broadcast_pauli = (False, False)
            else:  # invalid broadcast
                valid = False
            if not unconnected_neighbors:
                syndrome += (passthrough_parity,)
                if passthrough_parity:  # invalid passthrough
                    valid = False

            stabilizer = _bits_to_int(
                chain.from_iterable(pauli_graph.support_on_nodes(stabilizer_nodes))
            )
            if _solve_linear_system(stabilizer_basis, stabilizer, update_basis=valid) is not None:
                continue
            if valid:
                valid_graphs.append((pauli_graph, broadcast_pauli, passthrough_parity))
                if len(stabilizer_basis) == stabilizer_length:
                    break
            else:
                invalid_graphs.append(pauli_graph)
                syndromes.append(sum(b << i for i, b in enumerate(syndrome)))

        # try to fix local constraint violations by multiplying with other invalid graphs
        all_one = (1 << len(syndrome)) - 1
        if not unconnected_neighbors:
            all_one ^= 1 << (len(syndrome) - 1)
        syndrome_basis, basis_pauli_graphs = {}, []
        for i, (pauli_graph, syndrome) in enumerate(zip(invalid_graphs, syndromes)):
            if len(stabilizer_basis) == stabilizer_length:
                break
            for j, target in enumerate((syndrome ^ all_one, syndrome)):
                indices = _solve_linear_system(syndrome_basis, target, update_basis=j == 1)
                if indices is None:
                    if j == 1:
                        basis_pauli_graphs.append(pauli_graph)
                    continue
                new_pauli_graph = _multiply_pauli_graphs(
                    [basis_pauli_graphs[k] for k in indices] + [pauli_graph]
                )

                supports = new_pauli_graph.support_on_nodes([current_node])
                passthrough_parity = sum(supports[1 - is_x_node]) % 2
                if all(supports[is_x_node]):
                    broadcast_pauli = broadcast_basis
                else:
                    broadcast_pauli = (False, False)

                stabilizer = _bits_to_int(
                    chain.from_iterable(new_pauli_graph.support_on_nodes(stabilizer_nodes))
                )
                if _solve_linear_system(stabilizer_basis, stabilizer) is not None:
                    continue
                valid_graphs.append((new_pauli_graph, broadcast_pauli, passthrough_parity))
                break

        # enumerate new branches
        pauli_graphs = []
        for pauli_graph, broadcast_pauli, passthrough_parity in valid_graphs:
            combined_pauli = tuple(map(operator.xor, broadcast_pauli, passthrough_basis))
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

            for i, out_paulis in enumerate(out_paulis_list):
                if i:
                    new_pauli_graph = copy(pauli_graph)
                    new_pauli_graph[current_node] = copy(pauli_graph[current_node])
                else:
                    new_pauli_graph = pauli_graph
                for n, pauli in out_paulis.items():
                    if i:
                        new_pauli_graph[n] = copy(pauli_graph[n])
                    new_pauli_graph.add_support(zx_graph, (current_node, n), pauli)
                pauli_graphs.append(new_pauli_graph)

        if not pauli_graphs:  # no valid correlation surface exists on this ZX graph
            return []
        frontier.extend(
            filter(
                lambda n: zx_graph.vertex_degree(n) > 1 and n not in explored_nodes,
                unexplored_neighbors,
            )
        )
        explored_leaves.extend(
            filter(lambda n: zx_graph.vertex_degree(n) == 1, unexplored_neighbors)
        )
        explored_nodes.add(current_node)
    return pauli_graphs


def _bits_to_int(bits: Iterable[bool]) -> int:
    """Convert a list of bits to an integer."""
    return sum(b << i for i, b in enumerate(bits))


def _solve_linear_system(
    basis: dict[int, tuple[int, int]], x: int, update_basis: bool = True
) -> Iterable[int] | None:
    mask = 1 << len(basis)
    while x:
        highest_bit = x.bit_length() - 1
        if highest_bit not in basis:
            if update_basis:
                basis[highest_bit] = (x, mask)
            return None
        pivot, pivot_mask = basis[highest_bit]
        x ^= pivot
        mask ^= pivot_mask
    return filter(lambda i: (mask >> i) & 1, range(len(basis)))


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
