"""Defines :class:`CorrelationSurface` and functions to find and build them from a ZX graph."""

from __future__ import annotations

import multiprocessing
import operator
from collections import ChainMap
from collections.abc import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    MutableMapping,
    Sequence,
)
from copy import copy
from functools import cache, partial, reduce
from itertools import (
    accumulate,
    chain,
    combinations,
    pairwise,
    product,
    repeat,
    starmap,
)
from typing import Any, TypeVar

from pyzx.graph.graph_s import GraphS
from pyzx.utils import VertexType
from typing_extensions import Self

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.utils import (
    is_hadamard,
    vertex_type_to_pauli,
    zx_to_pauli,
)
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError


class _CorrelationSurfaceBase(MutableMapping[int, dict[int, Pauli]]):
    """Correlation surface represented as Pauli operators on half-edges."""

    def add_pauli_to_edge(
        self, edge: tuple[int, int], pauli: Pauli, edge_is_hadamard: bool
    ) -> Self:
        """Add Pauli operators to both ends of the given edge."""
        for (u, v), p in zip(
            (edge, edge[::-1]),
            (pauli, pauli.flipped(edge_is_hadamard)),
        ):
            edges = self.setdefault(u, {})
            edges[v] = p
        return self

    def paulis_at_nodes(self, nodes: Iterable[int]) -> Iterable[Pauli]:
        """Get the Pauli operators at the given nodes."""
        return chain.from_iterable(self[n].values() for n in nodes)

    def signature_at_nodes(
        self,
        nodes: Iterable[int],
        func: Callable[[Pauli], int] = lambda p: p.value,
        bit_length: int = 2,
    ) -> int:
        """Compute the signature at the given nodes using the provided function."""
        ints = self.paulis_at_nodes(nodes)
        return _concat_ints_as_bits(map(func, ints), bit_length)

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
            return broadcast_pauli, passthrough_parity  # type: ignore (broadcast_pauli is always bound here)
        return _concat_ints_as_bits(syndrome, 1)

    def to_immutable_public_representation(self, zx_graph: GraphS) -> CorrelationSurface:
        """Convert to the public representation of correlation surface."""
        span: list[ZXEdge] = []
        zx_nodes: dict[tuple[int, Basis], ZXNode] = {}
        bases = list(Basis)
        for u, v in zx_graph.edges():
            pauli_u = self[u][v]
            pauli_v = self[v][u]
            edge_is_hadamard = is_hadamard(zx_graph, (u, v))
            for xz_u, xz_v in product(Pauli.iter_xz(), repeat=2):
                if (edge_is_hadamard ^ (xz_u is xz_v)) and xz_u in pauli_u and xz_v in pauli_v:
                    basis_u = bases[xz_u.value >> 1]
                    basis_v = bases[xz_v.value >> 1]
                    node_u = zx_nodes.setdefault((u, basis_u), ZXNode(u, basis_u))
                    node_v = zx_nodes.setdefault((v, basis_v), ZXNode(v, basis_v))
                    span.append(ZXEdge.sorted(node_u, node_v))
        return CorrelationSurface(frozenset(span))


_CorrelationSurfaceType = TypeVar("_CorrelationSurfaceType", bound="_CorrelationSurfaceBase")


# Due to subtle differences in how generics and overloads are defined in the stubs, the type
# checker will say that dict.get is not a strictly valid replacement for MutableMapping.get.
class _CorrelationSurface(dict[int, dict[int, Pauli]], _CorrelationSurfaceBase):  # type: ignore
    """Correlation surface represented as Pauli operators on half-edges."""

    ...


class _CorrelationSurfaceView(ChainMap[int, dict[int, Pauli]], _CorrelationSurfaceBase):
    """A view of multiple correlation surfaces representing a single one."""

    def __setitem__(self, key, value):
        for mapping in self.maps:
            if key in mapping:
                mapping[key] = value
                return
        self.maps[0][key] = value

    def __delitem__(self, key):
        for mapping in self.maps:
            if key in mapping:
                del mapping[key]
                return
        raise KeyError(key)


def _xor_correlation_surfaces(
    correlation_surfaces: list[_CorrelationSurfaceBase],
) -> _CorrelationSurface:
    """XOR multiple correlation surfaces together."""
    # This method is deliberately written in this verbose manner, rather than more concisely with
    # zip, reduce, etc., to avoid the slight overhead, which becomes noticeable at a large scale.
    result = _CorrelationSurface()
    others = correlation_surfaces[1:]
    for v, neighbors in correlation_surfaces[0].items():
        result_neighbors = result.setdefault(v, {})
        other_neighbor_rows = [cs[v] for cs in others]
        for n, pauli in neighbors.items():
            for neighbor_row in other_neighbor_rows:
                pauli ^= neighbor_row[n]  # noqa: PLW2901
            result_neighbors[n] = pauli
    return result


def _partition_graph_from_vertices(
    zx_graph: GraphS, vertices_list: Sequence[set[int]], add_cut_edge_as_boundary_node: bool = False
) -> tuple[list[GraphS], list[tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]]]]]:
    """Create subgraphs from given sets of vertices; optionally add boundary vertices at cuts."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415

    subgraphs = []
    cut_edges_map = {}
    added_vertices_list = []
    for vertices in vertices_list:
        subgraph = GraphS()
        input_vertices, output_vertices = {}, {}
        for v in vertices:
            subgraph.add_vertex_indexed(v)
            subgraph.set_type(v, zx_graph.type(v))
            subgraph.set_phase(v, zx_graph.phase(v))
        for v in vertices:
            for u in zx_graph.neighbors(v):
                if u in vertices:
                    if not subgraph.connected(u, v):
                        subgraph.add_edge((u, v), zx_graph.edge_type((u, v)))  # type: ignore (PyZX issue)
                elif add_cut_edge_as_boundary_node:
                    key = tuple(sorted((u, v)))
                    if key in cut_edges_map:
                        new_boundary_vertex = cut_edges_map[key]
                        input_vertices[new_boundary_vertex] = (v, u)
                    else:
                        new_boundary_vertex = -len(cut_edges_map) - 1
                        cut_edges_map[key] = new_boundary_vertex
                        output_vertices[new_boundary_vertex] = (v, u)
                    subgraph.add_vertex_indexed(new_boundary_vertex)
                    subgraph.set_type(new_boundary_vertex, VertexType.BOUNDARY)
                    subgraph.add_edge((v, new_boundary_vertex))
        subgraphs.append(subgraph)
        added_vertices_list.append((input_vertices, output_vertices))
    return subgraphs, added_vertices_list


def _partition_graph_into_connected_components(zx_graph: GraphS) -> list[GraphS]:
    """Partition the ZX graph into connected components."""
    visited = set()
    components = []
    for start_vertex in zx_graph.vertices():
        if start_vertex in visited:
            continue
        component_vertices = set()
        stack = [start_vertex]
        while stack:
            vertex = stack.pop()
            if vertex in visited:
                continue
            visited.add(vertex)
            component_vertices.add(vertex)
            stack.extend(
                neighbor for neighbor in zx_graph.neighbors(vertex) if neighbor not in visited
            )
        component = _partition_graph_from_vertices(zx_graph, [component_vertices], False)[0][0]
        components.append(component)
    return components


def _product_of_disconnected_correlation_surfaces(
    correlation_surfaces_list: Sequence[Sequence[_CorrelationSurfaceBase]],
) -> Iterator[_CorrelationSurfaceView]:
    """Generate correlation surfaces from the product of disconnected components."""
    return starmap(_CorrelationSurfaceView, product(*correlation_surfaces_list))


def _restore_correlation_surface_from_added_vertices(
    correlation_surface: _CorrelationSurfaceType,
    added_vertices: dict[int, tuple[int, int]],
) -> _CorrelationSurfaceType:
    """Restore the correlation surface by recovering the cut edges represented by boundary nodes."""
    for v, (u, w) in added_vertices.items():
        if u in correlation_surface and v in correlation_surface[u]:
            correlation_surface[u][w] = correlation_surface[u][v]
            del correlation_surface[u][v]
        if v in correlation_surface:
            del correlation_surface[v]
    return correlation_surface


def _find_correlation_surfaces_with_vertex_ordering(
    zx_graph: GraphS, vertex_ordering: Sequence[set[int]] | None = None, parallel: bool = False
) -> list[_CorrelationSurfaceView]:
    """Find the correlation surfaces based on a given vertex ordering."""
    if vertex_ordering is None:
        return list(
            _product_of_disconnected_correlation_surfaces(
                _find_correlation_surfaces(zx_graph, parallel)
            )
        )

    # partition the ZX graph and find correlation surface generators for each subgraph
    subgraphs, added_vertices_list = _partition_graph_from_vertices(zx_graph, vertex_ordering, True)
    if parallel and len(subgraphs) > 1:
        with multiprocessing.Pool() as pool:
            correlation_surfaces_list = pool.map(_find_correlation_surfaces, subgraphs)
    else:
        correlation_surfaces_list = list(map(_find_correlation_surfaces, subgraphs))

    # post-process the first subgraph
    out_vertices = added_vertices_list.pop(0)[1]
    valid_surfaces = list(
        _product_of_disconnected_correlation_surfaces(correlation_surfaces_list.pop(0))
    )
    stabilizers: list[dict[int, Pauli]] = [
        {
            v: p
            for v, p in zip(out_vertices, correlation_surface.paulis_at_nodes(out_vertices.keys()))
        }
        for correlation_surface in valid_surfaces
    ]  # the stabilizers need to be derived before the boundary vertices are restored
    valid_surfaces = [
        _restore_correlation_surface_from_added_vertices(g, out_vertices) for g in valid_surfaces
    ]

    # match the boundary stabilizers for the rest of the subgraphs
    for correlation_surfaces, (input_vertices, output_vertices) in zip(
        correlation_surfaces_list, added_vertices_list
    ):
        combinations = _product_of_disconnected_correlation_surfaces(correlation_surfaces)
        stabilizer_basis, basis_surfaces, invalid_stabilizer_indices = {}, [], []
        for i, stabilizer in enumerate(stabilizers):
            local_stabilizer = _concat_ints_as_bits(
                (
                    p.flipped(is_hadamard(zx_graph, input_vertices[v])).value
                    for v, p in stabilizer.items()
                    if v in input_vertices
                ),
                2,
            )
            for correlation_surface in combinations:
                _solve_linear_system(
                    stabilizer_basis, correlation_surface.signature_at_nodes(input_vertices.keys())
                )
                basis_surfaces.append(correlation_surface)
                indices = _solve_linear_system(
                    stabilizer_basis,
                    local_stabilizer,
                    False,
                )
                if indices is not None:
                    new_correlation_surface = _xor_correlation_surfaces(
                        [basis_surfaces[k] for k in indices]
                    )
                    stabilizer.update(
                        zip(
                            output_vertices,
                            new_correlation_surface.paulis_at_nodes(output_vertices.keys()),
                        )
                    )
                    for v in input_vertices.keys():
                        del stabilizer[v]
                    for vertices in (input_vertices, output_vertices):
                        _restore_correlation_surface_from_added_vertices(
                            new_correlation_surface, vertices
                        )
                    valid_surfaces[i].maps.append(new_correlation_surface)
                    break
            else:  # unsatisfiable stabilizer, remove it
                invalid_stabilizer_indices.append(i)
        stabilizers = [s for i, s in enumerate(stabilizers) if i not in invalid_stabilizer_indices]

    return valid_surfaces


def _find_correlation_surfaces(
    zx_graph: GraphS, parallel: bool = False
) -> list[list[_CorrelationSurface]]:
    """Find the correlation surface generators for each connected component in the graph."""
    components = [
        (component, min(v for v in component.vertices() if component.vertex_degree(v) == 1))
        for component in _partition_graph_into_connected_components(zx_graph)
    ]
    if parallel and len(components) > 1:
        with multiprocessing.Pool() as pool:
            correlation_surfaces = pool.starmap(_find_correlation_surfaces_from_leaf, components)
    else:
        correlation_surfaces = list(starmap(_find_correlation_surfaces_from_leaf, components))
    return correlation_surfaces


def _find_correlation_surfaces_from_leaf(zx_graph: GraphS, leaf: int) -> list[_CorrelationSurface]:
    """Find the correlation surface generators satisfying the closed ports."""
    correlation_surfaces = _find_correlation_surface_generating_set_from_leaf(zx_graph, leaf)

    leaves = {pauli: [] for pauli in Pauli.iter_ixzy()}
    for v in filter(
        lambda v: zx_graph.vertex_degree(v) == 1,
        zx_graph.vertices(),
    ):
        leaves[zx_to_pauli(zx_graph, v).flipped()].append(v)
    open_leaves = leaves.pop(Pauli.I)

    if sum(len(leaves) for leaves in leaves.values()):
        correlation_surfaces = _reform_correlation_surface_generators(
            correlation_surfaces,
            lambda cs: _concat_ints_as_bits(
                (
                    cs.signature_at_nodes(leaves, lambda p: p not in (Pauli.I, pauli), 1)
                    for pauli, leaves in leaves.items()
                ),
                map(len, leaves.values()),
            ),
            stabilizer_basis={},
            basis_surfaces=[],
        )[1]

    if open_leaves:
        correlation_surfaces = [
            _xor_correlation_surfaces([correlation_surfaces[i] for i in indices])
            if len(indices := _int_to_bit_indices(mask)) > 1
            else correlation_surfaces[indices[0]]  # type: ignore (indices is always non-empty)
            for _, mask in _normalize_basis(
                _construct_basis(
                    {},
                    correlation_surfaces,
                    lambda cs: cs.signature_at_nodes(open_leaves),
                )
            ).values()
        ]

    return correlation_surfaces  # ty: ignore (seems to be a false positive of ty)


def _reform_correlation_surface_generators(
    correlation_surfaces: Iterable[_CorrelationSurfaceType],
    signature_func: Callable[[_CorrelationSurfaceType], int],
    stabilizer_basis: dict[int, tuple[int, int]],
    basis_surfaces: Sequence[_CorrelationSurfaceType],
    construct_new_surfaces: bool = True,
    num_new_surfaces_needed: int | None = None,
    num_basis_surfaces_needed: int | None = None,
) -> tuple[list[_CorrelationSurfaceType], list[_CorrelationSurface]]:
    """Reform the correlation surface generators based on the given signature function."""
    basis_surfaces, new_surfaces = list(basis_surfaces), []
    for correlation_surface in correlation_surfaces:
        indices = _solve_linear_system(
            stabilizer_basis,
            signature_func(correlation_surface),
        )
        if indices is None:
            basis_surfaces.append(correlation_surface)
            if (
                num_basis_surfaces_needed is not None
                and len(basis_surfaces) >= num_basis_surfaces_needed
            ):
                break
            continue
        if construct_new_surfaces:
            new_surfaces.append(
                _xor_correlation_surfaces(
                    [*(basis_surfaces[k] for k in indices), correlation_surface]
                )
            )
            if num_new_surfaces_needed is not None and len(new_surfaces) >= num_new_surfaces_needed:
                break
    return basis_surfaces, new_surfaces


@cache
def _generate_valid_local_paulis(
    node_basis: Pauli,
    broadcast_pauli: Pauli,
    passthrough_parity: bool,
    num_unconnected_neighbors: int,
    generate_all: bool = False,
) -> list[list[Pauli]]:
    """Generate valid local Pauli configurations given broadcast and passthrough status."""
    unconnected_neighbors = range(num_unconnected_neighbors)
    combined_pauli = broadcast_pauli ^ node_basis
    if generate_all:
        passthrough_nodes = chain.from_iterable(
            combinations(unconnected_neighbors, num_passthrough)
            for num_passthrough in range(
                passthrough_parity,
                len(unconnected_neighbors) + 1,
                2,
            )
        )
        out_paulis_list = [
            [
                combined_pauli if n in passthrough_nodes else broadcast_pauli
                for n in unconnected_neighbors
            ]
            for passthrough_nodes in passthrough_nodes
        ]
    else:
        passthrough_nodes = (
            ((n,) for n in unconnected_neighbors)
            if passthrough_parity
            else pairwise(unconnected_neighbors)
        )
        out_paulis_list = [
            [combined_pauli if n in m else broadcast_pauli for n in unconnected_neighbors]
            for m in passthrough_nodes
        ]
        if not passthrough_parity or not num_unconnected_neighbors:
            out_paulis_list.append([broadcast_pauli] * num_unconnected_neighbors)
    return out_paulis_list


def _expand_correlation_surface_to_node(
    correlation_surface: _CorrelationSurface,
    broadcast_pauli: Pauli,
    passthrough_parity: bool,
    node: int,
    node_basis: Pauli,
    unconnected_neighbors: list[int],
    edges_are_hadamard: list[bool],
    generate_all: bool = True,
    always_copy: bool = False,
) -> Generator[_CorrelationSurface, None]:
    """Expand to a generating set of correlation surfaces for the new node."""
    for i, out_paulis in enumerate(
        _generate_valid_local_paulis(
            node_basis,
            broadcast_pauli,
            passthrough_parity,
            len(unconnected_neighbors),
            generate_all=generate_all,  # generate all can reduce the gaussian elimination overhead
        )
    ):
        if i or always_copy:
            new_correlation_surface = copy(correlation_surface)
            new_correlation_surface[node] = copy(correlation_surface[node])
        else:
            new_correlation_surface = correlation_surface
        for n, pauli, edge_is_hadamard in zip(
            unconnected_neighbors, out_paulis, edges_are_hadamard
        ):
            if (i or always_copy) and n in correlation_surface:
                new_correlation_surface[n] = copy(correlation_surface[n])
            new_correlation_surface.add_pauli_to_edge((node, n), pauli, edge_is_hadamard)
        yield new_correlation_surface


def _find_correlation_surface_generating_set_from_leaf(
    zx_graph: GraphS, leaf: int
) -> list[_CorrelationSurface]:
    """Find a generating set of correlation surfaces assuming all ports are open."""
    neighbor: int = next(iter(zx_graph.neighbors(leaf)))
    correlation_surfaces = (
        _CorrelationSurface().add_pauli_to_edge(
            (leaf, neighbor), pauli, is_hadamard(zx_graph, (leaf, neighbor))
        )
        for pauli in Pauli.iter_xz()
    )
    if zx_graph.vertex_degree(neighbor) == 1:
        # edge case, make sure no leaf node will be in the frontier
        return list(correlation_surfaces)
    frontier = [neighbor]
    explored_leaves = [leaf]
    explored_nodes = {leaf}
    correlation_surface = next(correlation_surfaces)

    while frontier:
        current_node = frontier.pop(0)
        connected_neighbors = list(correlation_surface[current_node].keys())
        unconnected_neighbors = list(
            filter(
                lambda n: n not in connected_neighbors,
                zx_graph.neighbors(current_node),
            )
        )
        boundary_nodes = explored_leaves + frontier
        if unconnected_neighbors:
            boundary_nodes.append(current_node)
        generating_set_size = sum(len(correlation_surface[n]) for n in boundary_nodes)
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in correlation_surface]
        passthrough_basis = zx_to_pauli(zx_graph, current_node)

        # check if each correlation surface candidate satisfies broadcast and passthrough rules
        # on the current node and is not a product of previously checked valid correlation surfaces
        valid_surfaces, invalid_surfaces, syndromes, vector_basis = [], [], [], {}
        for correlation_surface in chain([correlation_surface], correlation_surfaces):
            constraint_check = correlation_surface.validate_node(
                current_node, passthrough_basis, bool(unconnected_neighbors)
            )
            if isinstance(constraint_check, int):  # invalid
                invalid_surfaces.append(correlation_surface)
                syndromes.append(constraint_check)
                continue
            if (
                _solve_linear_system(
                    vector_basis, correlation_surface.signature_at_nodes(boundary_nodes)
                )
                is None
            ):  # new independent surface
                valid_surfaces.append((correlation_surface, *constraint_check))
                if len(vector_basis) == generating_set_size:
                    break

        # try to fix local constraint violations by XORing with other invalid surfaces
        all_one = (1 << len(connected_neighbors)) - 1
        syndrome_basis, basis_surfaces = {}, []
        for correlation_surface, syndrome in zip(invalid_surfaces, syndromes):
            if len(vector_basis) == generating_set_size:
                break
            for j, target in enumerate((syndrome ^ all_one, syndrome)):  # two valid options
                indices = _solve_linear_system(syndrome_basis, target, update_basis=j == 1)
                if indices is None:
                    if j == 1:
                        basis_surfaces.append(correlation_surface)
                    continue
                new_correlation_surface = _xor_correlation_surfaces(
                    [*(basis_surfaces[k] for k in indices), correlation_surface]
                )
                if (
                    _solve_linear_system(
                        vector_basis, new_correlation_surface.signature_at_nodes(boundary_nodes)
                    )
                    is None
                ):
                    valid_surfaces.append(
                        (
                            new_correlation_surface,
                            *new_correlation_surface.validate_node(
                                current_node, passthrough_basis, bool(unconnected_neighbors)
                            ),  # type: ignore (the new surface is always valid so it's always a tuple)
                        )
                    )
                    break

        # enumerate new branches
        correlation_surfaces = chain.from_iterable(
            starmap(
                partial(
                    _expand_correlation_surface_to_node,
                    node=current_node,
                    node_basis=passthrough_basis,
                    unconnected_neighbors=unconnected_neighbors,
                    edges_are_hadamard=[
                        is_hadamard(zx_graph, (current_node, n)) for n in unconnected_neighbors
                    ],
                    # always_copy=True,  # can be False if the exploration is BFS
                ),
                valid_surfaces,
            )
        )
        correlation_surface = next(correlation_surfaces, None)
        if not correlation_surface:  # no valid correlation surface exists on this ZX graph
            return []
        frontier.extend(
            filter(
                lambda n: n not in explored_nodes and zx_graph.vertex_degree(n) > 1,
                unexplored_neighbors,
            )
        )
        explored_leaves.extend(
            filter(lambda n: zx_graph.vertex_degree(n) == 1, unexplored_neighbors)
        )
        explored_nodes.add(current_node)

    # eliminate dependent surfaces from the final expansion to get a generating set
    return _reform_correlation_surface_generators(
        [correlation_surface, *correlation_surfaces],
        lambda cs: cs.signature_at_nodes(
            filter(
                lambda v: zx_graph.vertex_degree(v) == 1,
                zx_graph.vertices(),
            )
        ),
        stabilizer_basis={},
        basis_surfaces=[],
        construct_new_surfaces=False,
        num_basis_surfaces_needed=len(
            [v for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1]
        ),
    )[0]


def _concat_ints_as_bits(ints: Iterable[int], bit_length: int | Iterable[int]) -> int:
    """Concatenate a list of integers as bits to form a single integer."""
    if isinstance(bit_length, int):
        bit_length = repeat(bit_length)
    return sum(x << shift for x, shift in zip(ints, chain([0], accumulate(bit_length))))


def _solve_linear_system(
    basis: dict[int, tuple[int, int]], x: int, update_basis: bool = True
) -> tuple[int, ...] | None:
    """Gaussian elimination over GF(2)."""
    mask = 1 << len(basis)
    while x:
        highest_bit = x.bit_length() - 1
        if highest_bit not in basis:
            if update_basis:
                basis[highest_bit] = (x, mask)
            return
        pivot, pivot_mask = basis[highest_bit]
        x ^= pivot
        mask ^= pivot_mask
    return _int_to_bit_indices(mask)[:-1]


def _int_to_bit_indices(x: int) -> tuple[int, ...]:
    """Convert an integer to a list of indices where the bits are set."""
    return tuple(i for i in range(x.bit_length()) if (x >> i) & 1)


def _construct_basis(
    basis: dict[int, tuple[int, int]], items: Iterable[Any], func: Callable[[Any], int]
) -> dict[int, tuple[int, int]]:
    """Construct a linear basis from the given items using the provided function."""
    for item in items:
        _solve_linear_system(basis, func(item))
    return basis


def _normalize_basis(
    basis: dict[int, tuple[int, int]], in_place: bool = True
) -> dict[int, tuple[int, int]]:
    """Normalize the basis vectors to only have leading 1s when possible."""
    normalized_basis = basis if in_place else {}
    highest_bits = sorted(basis, reverse=True)
    for i, key in enumerate(highest_bits):
        vector, mask = basis[key]
        for highest_bit in highest_bits[i + 1 :]:
            if (vector >> highest_bit) & 1:
                pivot, pivot_mask = basis[highest_bit]
                vector ^= pivot
                mask ^= pivot_mask
        normalized_basis[key] = (vector, mask)
    return normalized_basis


def _check_spiders_are_supported(g: GraphS) -> None:
    """Check the preconditions for the correlation surface finding algorithm."""
    for v in g.vertices():
        # 1. Check the spider types and phases are supported
        vt = g.type(v)
        phase = g.phase(v)
        try:
            pauli = vertex_type_to_pauli(vt, phase)
        except TQECError:
            raise TQECError(f"Unsupported spider type and phase: {vt} and {phase}.")
        # 2. Check degree of the spiders
        degree = g.vertex_degree(v)
        if pauli is Pauli.I and degree != 1:
            raise TQECError(f"Boundary spider must be dangling, but got {degree} neighbors.")
        if pauli is Pauli.Y and degree != 1:
            raise TQECError(f"S spider must be dangling, but got {degree} neighbors.")
