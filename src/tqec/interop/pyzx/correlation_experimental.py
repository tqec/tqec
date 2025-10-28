"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

from __future__ import annotations

import heapq
import operator
from collections.abc import Callable, Generator, Iterable
from copy import copy
from enum import IntFlag
from fractions import Fraction
from functools import partial, reduce
from itertools import accumulate, chain, pairwise, product, repeat, starmap

import stim
from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb, multiply_paulis
from pyzx.utils import FractionLike, VertexType

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.utils import is_boundary, is_s, is_z_no_phase
from tqec.interop.pyzx.utils import is_hardmard as is_hadamard
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
            span.add(ZXEdge(ZXNode(u, Basis.X), ZXNode(v, Basis.X)))
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
    correlation_surfaces = _find_correlation_surfaces_from_leaf(g, min(leaves))

    # if CorrelationSurface(frozenset()) in correlation_surfaces:
    #     correlation_surfaces.remove(CorrelationSurface(frozenset()))

    # sort the correlation surfaces to make the result deterministic
    return sorted(correlation_surfaces, key=lambda x: sorted(x.span))


class Pauli(IntFlag):
    """Pauli operators as bit flags of X and Z supports."""

    I = 0  # noqa: E741
    X = 1
    Z = 2
    Y = X | Z

    def flipped(self) -> Pauli:
        """Return the Pauli operator with X and Z supports flipped."""
        return Pauli((self >> 1) | ((self % 2) << 1))


PAULIS_XZ = (Pauli.X, Pauli.Z)
PAULIS_XYZ = (Pauli.X, Pauli.Y, Pauli.Z)


class PauliGraph(dict[int, dict[int, Pauli]]):
    """Correlation surface represented as X and Z supports on half-edges."""

    def add_pauli_to_edge(
        self, edge: tuple[int, int], pauli: Pauli, edge_is_hadamard: bool
    ) -> PauliGraph:
        """Add Pauli operators to both ends of the given edge."""
        for (u, v), p in zip(
            (edge, edge[::-1]),
            (
                pauli,
                pauli.flipped() if edge_is_hadamard else pauli,
            ),
        ):
            edges = self.setdefault(u, {})
            edges[v] = p
        return self

    def paulis_at_nodes(self, nodes: list[int]) -> Iterable[Pauli]:
        """Get the Pauli operators at the given nodes."""
        return chain.from_iterable(self[n].values() for n in nodes)

    def signature_at_nodes(
        self,
        nodes: list[int],
        func: Callable[[Pauli], int] | None = None,
        bit_length: int = 2,
    ) -> int:
        """Compute the signature at the given nodes using the provided function."""
        ints = self.paulis_at_nodes(nodes)
        if func is not None:
            ints = map(func, ints)
        return _concat_ints_as_bits(ints, bit_length)

    def validate_node(
        self, node: int, node_basis: Pauli, has_unconnected_neighbors: bool
    ) -> int | tuple[Pauli, bool]:
        """Return the broadcast Pauli and passthrough parity if valid or the syndrome otherwise."""
        paulis = list(self.paulis_at_nodes([node]))
        passthrough_parity = node_basis in reduce(operator.xor, paulis)
        valid = True
        broadcast_basis = node_basis.flipped()
        syndrome = [broadcast_basis in pauli for pauli in paulis]
        if all(syndrome):
            broadcast_pauli = broadcast_basis
        elif not any(syndrome):
            broadcast_pauli = Pauli.I
        else:  # invalid broadcast
            valid = False
        if not has_unconnected_neighbors:
            syndrome.append(passthrough_parity)
            if passthrough_parity:  # invalid passthrough
                valid = False
        if valid:
            return broadcast_pauli, passthrough_parity
        return _concat_ints_as_bits(syndrome, 1)

    def to_correlation_surface(self, zx_graph: GraphS) -> CorrelationSurface:
        """Convert a PauliGraph to a CorrelationSurface."""
        span = []
        bases = list(Basis)
        for u, v in zx_graph.edges():
            pauli_u = self[u][v]
            pauli_v = self[v][u]
            edge_is_hadamard = is_hadamard(zx_graph, (u, v))
            for basis_u, basis_v in product(PAULIS_XZ, repeat=2):
                if (
                    (edge_is_hadamard ^ (basis_u == basis_v))
                    and basis_u in pauli_u
                    and basis_v in pauli_v
                ):
                    span.append(
                        ZXEdge(ZXNode(u, bases[basis_u >> 1]), ZXNode(v, bases[basis_v >> 1]))
                    )
        return CorrelationSurface(frozenset(span))


def _multiply_pauli_graphs(pauli_graphs: list[PauliGraph]) -> PauliGraph:
    result = PauliGraph()
    others = pauli_graphs[1:]
    for v, neighbors in pauli_graphs[0].items():
        result_neighbors = result.setdefault(v, {})
        other_neighbor_rows = [pg[v] for pg in others]
        for n, pauli in neighbors.items():
            for neighbor_row in other_neighbor_rows:
                pauli ^= neighbor_row[n]  # noqa: PLW2901
            result_neighbors[n] = pauli
    return result


def _expand_pauli_graph_to_node(
    pauli_graph: PauliGraph,
    broadcast_pauli: Pauli,
    passthrough_parity: bool,
    node: int,
    node_basis: Pauli,
    unconnected_neighbors: list[int],
    edges_are_hadamard: list[bool],
    always_copy: bool = False,
) -> Generator[PauliGraph, None]:
    """Expand to a generator set of Pauli graphs for the new node."""
    combined_pauli = broadcast_pauli ^ node_basis
    passthrough_nodes = (
        ([n] for n in unconnected_neighbors)
        if passthrough_parity
        else pairwise(unconnected_neighbors)
    )
    out_paulis_list = [
        [combined_pauli if n in m else broadcast_pauli for n in unconnected_neighbors]
        for m in passthrough_nodes
    ]
    if not passthrough_parity or not unconnected_neighbors:
        out_paulis_list.append([broadcast_pauli] * len(unconnected_neighbors))

    for i, out_paulis in enumerate(out_paulis_list):
        if i or always_copy:
            new_pauli_graph = copy(pauli_graph)
            new_pauli_graph[node] = copy(pauli_graph[node])
        else:
            new_pauli_graph = pauli_graph
        for n, pauli, edge_is_hadamard in zip(
            unconnected_neighbors, out_paulis, edges_are_hadamard
        ):
            if (i or always_copy) and n in pauli_graph:
                new_pauli_graph[n] = copy(pauli_graph[n])
            new_pauli_graph.add_pauli_to_edge((node, n), pauli, edge_is_hadamard)
        yield new_pauli_graph


def _find_correlation_surfaces_from_leaf(zx_graph: GraphS, leaf: int) -> list[CorrelationSurface]:
    closed_leaves = {pauli: [] for pauli in PAULIS_XYZ}
    for closed_leaf in filter(
        lambda v: zx_graph.vertex_degree(v) == 1 and not is_boundary(zx_graph, v),
        zx_graph.vertices(),
    ):
        if is_s(zx_graph, closed_leaf):
            closed_leaves[Pauli.Y].append(closed_leaf)
        elif is_z_no_phase(zx_graph, closed_leaf):
            closed_leaves[Pauli.X].append(closed_leaf)
        else:
            closed_leaves[Pauli.Z].append(closed_leaf)

    pauli_graphs = _find_pauli_graph_generator_set_from_leaf(zx_graph, leaf)
    if sum(len(leaves) for leaves in closed_leaves.values()):
        stabilizer_basis, basis_pauli_graphs, valid_pauli_graphs = {}, [], []
        for pauli_graph in pauli_graphs:
            indices = _solve_linear_system(
                stabilizer_basis,
                _concat_ints_as_bits(
                    (
                        pauli_graph.signature_at_nodes(
                            leaves, lambda p: p not in (Pauli.I, pauli), 1
                        )
                        for pauli, leaves in closed_leaves.items()
                    ),
                    map(len, closed_leaves.values()),
                ),
            )
            if indices is None:
                basis_pauli_graphs.append(pauli_graph)
                continue
            valid_pauli_graphs.append(
                _multiply_pauli_graphs([*(basis_pauli_graphs[k] for k in indices), pauli_graph])
            )
        pauli_graphs = valid_pauli_graphs
    return [pg.to_correlation_surface(zx_graph) for pg in pauli_graphs]


def _find_pauli_graph_generator_set_from_leaf(zx_graph: GraphS, leaf: int) -> list[PauliGraph]:
    """Find the correlation surfaces starting from a leaf node in the graph."""
    neighbor: int = next(iter(zx_graph.neighbors(leaf)))
    pauli_graphs: list[PauliGraph] = [
        PauliGraph().add_pauli_to_edge(
            (leaf, neighbor), pauli, is_hadamard(zx_graph, (leaf, neighbor))
        )
        for pauli in PAULIS_XZ
    ]
    if zx_graph.vertex_degree(neighbor) == 1:  # make sure no leaf node will be in the frontier
        return pauli_graphs
    frontier = [neighbor]
    explored_leaves = [leaf]
    explored_nodes = {leaf}

    while frontier:
        current_node = heapq.heappop(frontier)
        connected_neighbors = list(pauli_graphs[0][current_node].keys())
        unconnected_neighbors = list(
            filter(
                lambda n: n not in connected_neighbors,
                zx_graph.neighbors(current_node),
            )
        )
        boundary_nodes = explored_leaves + frontier
        if unconnected_neighbors:
            boundary_nodes.append(current_node)
        generator_set_size = sum(len(pauli_graphs[0][n]) for n in boundary_nodes)
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in pauli_graphs[0]]
        passthrough_basis = Pauli(1 << (zx_graph.type(current_node) == VertexType.Z))

        # check if each Pauli graph candidate satisfies broadcast and passthrough constraints
        # on the current node and is not a product of previously checked valid Pauli graphs
        valid_graphs, invalid_graphs, syndromes, vector_basis = [], [], [], {}
        for pauli_graph in pauli_graphs:
            constraint_check = pauli_graph.validate_node(
                current_node, passthrough_basis, bool(unconnected_neighbors)
            )
            if isinstance(constraint_check, int):  # invalid
                invalid_graphs.append(pauli_graph)
                syndromes.append(constraint_check)
                continue
            if (
                _solve_linear_system(vector_basis, pauli_graph.signature_at_nodes(boundary_nodes))
                is None
            ):  # new independent graph
                valid_graphs.append((pauli_graph, *constraint_check))
                if len(vector_basis) == generator_set_size:
                    break

        # try to fix local constraint violations by multiplying with other invalid graphs
        all_one = (1 << len(connected_neighbors)) - 1
        syndrome_basis, basis_pauli_graphs = {}, []
        for pauli_graph, syndrome in zip(invalid_graphs, syndromes):
            if len(vector_basis) == generator_set_size:
                break
            for j, target in enumerate((syndrome ^ all_one, syndrome)):  # two valid options
                indices = _solve_linear_system(syndrome_basis, target, update_basis=j == 1)
                if indices is None:
                    if j == 1:
                        basis_pauli_graphs.append(pauli_graph)
                    continue
                new_pauli_graph = _multiply_pauli_graphs(
                    [*(basis_pauli_graphs[k] for k in indices), pauli_graph]
                )
                if (
                    _solve_linear_system(
                        vector_basis, new_pauli_graph.signature_at_nodes(boundary_nodes)
                    )
                    is None
                ):
                    valid_graphs.append(
                        (
                            new_pauli_graph,
                            *new_pauli_graph.validate_node(
                                current_node, passthrough_basis, bool(unconnected_neighbors)
                            ),
                        )
                    )
                    break

        # enumerate new branches
        pauli_graphs = list(
            chain.from_iterable(
                starmap(
                    partial(
                        _expand_pauli_graph_to_node,
                        node=current_node,
                        node_basis=passthrough_basis,
                        unconnected_neighbors=unconnected_neighbors,
                        edges_are_hadamard=[
                            is_hadamard(zx_graph, (current_node, n)) for n in unconnected_neighbors
                        ],
                        always_copy=True,  # can be False if the exploration is BFS
                    ),
                    valid_graphs,
                )
            )
        )

        if not pauli_graphs:  # no valid correlation surface exists on this ZX graph
            return []
        for n in unexplored_neighbors:
            if n not in explored_nodes and zx_graph.vertex_degree(n) > 1:
                heapq.heappush(frontier, n)
        explored_leaves.extend(
            filter(lambda n: zx_graph.vertex_degree(n) == 1, unexplored_neighbors)
        )
        explored_nodes.add(current_node)
    return pauli_graphs


def _concat_ints_as_bits(ints: Iterable[int], bit_length: int | Iterable[int]) -> int:
    """Concatenate a list of integers as bits to form a single integer."""
    if isinstance(bit_length, int):
        bit_length = repeat(bit_length)
    return sum(x << shift for x, shift in zip(ints, chain([0], accumulate(bit_length))))


def _solve_linear_system(
    basis: dict[int, tuple[int, int]], x: int, update_basis: bool = True
) -> list[int] | None:
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
    return list(filter(lambda i: (mask >> i) & 1, range(len(basis))))


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
