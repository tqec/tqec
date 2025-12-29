"""Defines the :class:`.CorrelationSurface` class and functions to find them in a ZX graph."""

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
from enum import IntFlag
from fractions import Fraction
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

import stim
from pyzx.graph.graph_s import GraphS
from pyzx.pauliweb import PauliWeb, multiply_paulis
from pyzx.utils import FractionLike, VertexType
from typing_extensions import Self

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.utils import is_boundary, is_hadamard, is_s, is_z_no_phase
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
            span.add(ZXEdge(ZXNode(u, Basis.X), ZXNode(v, Basis.X)))
            span.add(ZXEdge(ZXNode(u, Basis.Z), ZXNode(v, Basis.Z)))
            continue
        span.add(ZXEdge(ZXNode(u, Basis(pauli_u)), ZXNode(v, Basis(pauli_v))))
    return CorrelationSurface(frozenset(span))


def find_correlation_surfaces(
    g: GraphS,
    vertex_ordering: Sequence[set[int]] | None = None,
    parallel: bool = False,
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
    3. Reform the generators so that they satisfy the closed ports.
    4. Reform the generators so that the number of Y-terminating correlation surfaces is minimized.
    5. Combine the generators from all connected components.

    The rules for generating valid correlation surfaces at each node are as follows. For a node of
    basis B in {X, Z}:
    - *broadcast rule:* All or none of the incident edges supports the opposite of B.
    - *passthrough rule:* An even number of incident edges supports B.

    For leaf nodes:
    - For an X/Z type leaf node, it can only support the logical observable with the opposite type.
      Only a single type of logical observable is explored from the leaf node.
    - For a Y type leaf node, it can only support the Y logical observable, i.e. the presence of
      both X and Z logical observable. Both X and Z type logical observable are explored from the
      leaf node. And the two correlation surfaces are combined to form the Y type correlation
      surface.
    - For the BOUNDARY node, it can support any type of logical observable. Both X and Z type
      logical observable are explored from it.

    Args:
        g: The ZX graph to find the correlation surfaces.
        vertex_ordering: A reserved argument for an unfinished feature. Should not be used at this
            moment.
        parallel: Whether to use multiprocessing to speed up the computation. Only applies to
            embarrassingly parallel parts of the algorithm. Default is `False`.

    Returns:
        A list of `CorrelationSurface` in the graph.

    """
    if vertex_ordering is not None:
        raise NotImplementedError(
            "The `vertex_ordering` argument is reserved for an unfinished feature and should not"
            " be used at this moment."
        )
    _check_spiders_are_supported(g)
    # Edge case: single node graph
    if g.num_vertices() == 1:
        v = next(iter(g.vertices()))
        basis = Basis.X if is_z_no_phase(g, v) else Basis.Z
        node = ZXNode(v, basis)
        return [CorrelationSurface(frozenset({ZXEdge(node, node)}))]

    leaves = {v for v in g.vertices() if g.vertex_degree(v) == 1}
    if not leaves:
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )

    # sort the correlation surfaces to make the result deterministic
    return sorted(
        (
            cs.to_correlation_surface(g)
            for cs in _find_pauli_graphs_with_vertex_ordering(g, vertex_ordering, parallel)
        ),
        key=lambda x: sorted(x.span),
    )


class Pauli(IntFlag):
    """Pauli operators as bit flags of X and Z supports."""

    I = 0  # noqa: E741
    X = 1
    Z = 2
    Y = X | Z

    def flipped(self) -> Pauli:
        """Return the Pauli operator with X and Z supports flipped."""
        return Pauli((self >> 1) | ((self % 2) << 1))


# Directly iterating over Pauli gives X, Z in Python 3.11+ but I, X, Y, Z in 3.10 due to a behavior
# change in Flag. So we define these tuples for consistent behavior across versions.
PAULIS_XZ = (Pauli.X, Pauli.Z)
PAULIS_XYZ = (Pauli.X, Pauli.Y, Pauli.Z)
PAULIS_IXYZ = (Pauli.I, Pauli.X, Pauli.Y, Pauli.Z)


class PauliGraphBase(MutableMapping[int, dict[int, Pauli]]):
    """Correlation surface represented as Pauli operators on half-edges."""

    def add_pauli_to_edge(
        self, edge: tuple[int, int], pauli: Pauli, edge_is_hadamard: bool
    ) -> Self:
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

    def paulis_at_nodes(self, nodes: Iterable[int]) -> Iterable[Pauli]:
        """Get the Pauli operators at the given nodes."""
        return chain.from_iterable(self[n].values() for n in nodes)

    def signature_at_nodes(
        self,
        nodes: Iterable[int],
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
            return broadcast_pauli, passthrough_parity  # type: ignore (broadcast_pauli is always bound here)
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


PauliGraphType = TypeVar("PauliGraphType", bound="PauliGraphBase")


# Due to subtle differences in how generics and overloads are defined in the stubs, the type
# checker will say that dict.get is not a strictly valid replacement for MutableMapping.get.
class PauliGraph(dict[int, dict[int, Pauli]], PauliGraphBase):  # type: ignore
    """Correlation surface represented as Pauli operators on half-edges."""

    ...


class PauliGraphView(ChainMap[int, dict[int, Pauli]], PauliGraphBase):
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


def _multiply_pauli_graphs(pauli_graphs: list[PauliGraphBase]) -> PauliGraph:
    """Multiply multiple correlation surfaces together."""
    # This method is deliberately written in this verbose manner, rather than more concisely with
    # zip, reduce, etc., to avoid the slight overhead, which becomes noticeable at a large scale.
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


def _partition_graph_from_vertices(
    zx_graph: GraphS, vertices_list: Sequence[set[int]], add_cut_edge_as_boundary_node: bool = False
) -> tuple[list[GraphS], list[tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]]]]]:
    """Create subgraphs from given sets of vertices; optionally add boundary vertices at cuts."""
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


def _product_of_disconnected_pauli_graphs(
    pauli_graphs_list: Sequence[Sequence[PauliGraphBase]],
) -> Iterator[PauliGraphView]:
    """Generate Pauli graphs from the product of disconnected components."""
    return starmap(PauliGraphView, product(*pauli_graphs_list))


def _restore_pauli_graph_from_added_vertices(
    pauli_graph: PauliGraphType,
    added_vertices: dict[int, tuple[int, int]],
) -> PauliGraphType:
    """Restore the Pauli graph by recovering the cut edges represented by boundary nodes."""
    for v, (u, w) in added_vertices.items():
        if u in pauli_graph and v in pauli_graph[u]:
            pauli_graph[u][w] = pauli_graph[u][v]
            del pauli_graph[u][v]
        if v in pauli_graph:
            del pauli_graph[v]
    return pauli_graph


def _find_pauli_graphs_with_vertex_ordering(
    zx_graph: GraphS, vertex_ordering: Sequence[set[int]] | None = None, parallel: bool = False
) -> list[PauliGraphView]:
    """Find the correlation surfaces based on a given vertex ordering."""
    if vertex_ordering is None:
        return list(_product_of_disconnected_pauli_graphs(_find_pauli_graphs(zx_graph, parallel)))

    # partition the ZX graph and find correlation surface generators for each subgraph
    subgraphs, added_vertices_list = _partition_graph_from_vertices(zx_graph, vertex_ordering, True)
    if parallel and len(subgraphs) > 1:
        with multiprocessing.Pool() as pool:
            pauli_graphs_list = pool.map(_find_pauli_graphs, subgraphs)
    else:
        pauli_graphs_list = list(map(_find_pauli_graphs, subgraphs))

    # post-process the first subgraph
    out_vertices = added_vertices_list.pop(0)[1]
    valid_graphs = list(_product_of_disconnected_pauli_graphs(pauli_graphs_list.pop(0)))
    stabilizers: list[dict[int, Pauli]] = [
        {v: p for v, p in zip(out_vertices, pauli_graph.paulis_at_nodes(out_vertices.keys()))}
        for pauli_graph in valid_graphs
    ]  # the stabilizers need to be derived before the boundary vertices are restored
    valid_graphs = [_restore_pauli_graph_from_added_vertices(g, out_vertices) for g in valid_graphs]

    # match the boundary stabilizers for the rest of the subgraphs
    for pauli_graphs, (input_vertices, output_vertices) in zip(
        pauli_graphs_list, added_vertices_list
    ):
        combinations = _product_of_disconnected_pauli_graphs(pauli_graphs)
        stabilizer_basis, basis_graphs, invalid_stabilizer_indices = {}, [], []
        for i, stabilizer in enumerate(stabilizers):
            local_stabilizer = _concat_ints_as_bits(
                (
                    p.flipped() if is_hadamard(zx_graph, input_vertices[v]) else p
                    for v, p in stabilizer.items()
                    if v in input_vertices
                ),
                2,
            )
            for pauli_graph in combinations:
                _solve_linear_system(
                    stabilizer_basis, pauli_graph.signature_at_nodes(input_vertices.keys())
                )
                basis_graphs.append(pauli_graph)
                indices = _solve_linear_system(
                    stabilizer_basis,
                    local_stabilizer,
                    False,
                )
                if indices is not None:
                    new_pauli_graph = _multiply_pauli_graphs([basis_graphs[k] for k in indices])
                    stabilizer.update(
                        zip(
                            output_vertices, new_pauli_graph.paulis_at_nodes(output_vertices.keys())
                        )
                    )
                    for v in input_vertices.keys():
                        del stabilizer[v]
                    for vertices in (input_vertices, output_vertices):
                        _restore_pauli_graph_from_added_vertices(new_pauli_graph, vertices)
                    valid_graphs[i].maps.append(new_pauli_graph)
                    break
            else:  # unsatisfiable stabilizer, remove it
                invalid_stabilizer_indices.append(i)
        stabilizers = [s for i, s in enumerate(stabilizers) if i not in invalid_stabilizer_indices]

    return valid_graphs


def _find_pauli_graphs(zx_graph: GraphS, parallel: bool = False) -> list[list[PauliGraph]]:
    """Find the correlation surface generators for each connected component in the graph."""
    components = [
        (component, min(v for v in component.vertices() if component.vertex_degree(v) == 1))
        for component in _partition_graph_into_connected_components(zx_graph)
    ]
    if parallel and len(components) > 1:
        with multiprocessing.Pool() as pool:
            pauli_graphs = pool.starmap(_find_pauli_graphs_from_leaf, components)
    else:
        pauli_graphs = list(starmap(_find_pauli_graphs_from_leaf, components))
    return pauli_graphs


def _find_pauli_graphs_from_leaf(zx_graph: GraphS, leaf: int) -> list[PauliGraph]:
    """Find the correlation surface generators satisfying the closed ports."""
    pauli_graphs = _find_pauli_graph_generating_set_from_leaf(zx_graph, leaf)

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

    if sum(len(leaves) for leaves in closed_leaves.values()):
        pauli_graphs = _reform_pauli_graph_generators(
            pauli_graphs,
            lambda pg: _concat_ints_as_bits(
                (
                    pg.signature_at_nodes(leaves, lambda p: p not in (Pauli.I, pauli), 1)
                    for pauli, leaves in closed_leaves.items()
                ),
                map(len, closed_leaves.values()),
            ),
            stabilizer_basis={},
            basis_graphs=[],
        )[1]

    if open_leaves := list(
        filter(
            lambda v: zx_graph.vertex_degree(v) == 1 and is_boundary(zx_graph, v),
            zx_graph.vertices(),
        )
    ):
        pauli_graphs = [
            _multiply_pauli_graphs([pauli_graphs[i] for i in indices])
            if len(indices := _int_to_bit_indices(mask)) > 1
            else pauli_graphs[indices[0]]  # type: ignore (indices is always non-empty)
            for _, mask in _normalize_basis(
                _construct_basis(
                    {},
                    pauli_graphs,
                    lambda pg: pg.signature_at_nodes(open_leaves),
                )
            ).values()
        ]

    return pauli_graphs  # ty: ignore (seems to be a false positive of ty)


def _reform_pauli_graph_generators(
    pauli_graphs: Iterable[PauliGraphType],
    signature_func: Callable[[PauliGraphType], int],
    stabilizer_basis: dict[int, tuple[int, int]],
    basis_graphs: Sequence[PauliGraphType],
    construct_new_graphs: bool = True,
    num_new_graphs_needed: int | None = None,
    num_basis_graphs_needed: int | None = None,
) -> tuple[list[PauliGraphType], list[PauliGraph]]:
    """Reform the Pauli graph generators based on the given signature function."""
    basis_graphs, new_graphs = list(basis_graphs), []
    for pauli_graph in pauli_graphs:
        indices = _solve_linear_system(
            stabilizer_basis,
            signature_func(pauli_graph),
        )
        if indices is None:
            basis_graphs.append(pauli_graph)
            if num_basis_graphs_needed is not None and len(basis_graphs) >= num_basis_graphs_needed:
                break
            continue
        if construct_new_graphs:
            new_graphs.append(
                _multiply_pauli_graphs([*(basis_graphs[k] for k in indices), pauli_graph])
            )
            if num_new_graphs_needed is not None and len(new_graphs) >= num_new_graphs_needed:
                break
    return basis_graphs, new_graphs


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


def _expand_pauli_graph_to_node(
    pauli_graph: PauliGraph,
    broadcast_pauli: Pauli,
    passthrough_parity: bool,
    node: int,
    node_basis: Pauli,
    unconnected_neighbors: list[int],
    edges_are_hadamard: list[bool],
    generate_all: bool = True,
    always_copy: bool = False,
) -> Generator[PauliGraph, None]:
    """Expand to a generator set of Pauli graphs for the new node."""
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


def _find_pauli_graph_generating_set_from_leaf(zx_graph: GraphS, leaf: int) -> list[PauliGraph]:
    """Find a generating set of correlation surfaces assuming all ports are open."""
    neighbor: int = next(iter(zx_graph.neighbors(leaf)))
    pauli_graphs = (
        PauliGraph().add_pauli_to_edge(
            (leaf, neighbor), pauli, is_hadamard(zx_graph, (leaf, neighbor))
        )
        for pauli in PAULIS_XZ
    )
    if zx_graph.vertex_degree(neighbor) == 1:
        # edge case, make sure no leaf node will be in the frontier
        return list(pauli_graphs)
    frontier = [neighbor]
    explored_leaves = [leaf]
    explored_nodes = {leaf}
    pauli_graph = next(pauli_graphs)

    while frontier:
        current_node = frontier.pop(0)
        connected_neighbors = list(pauli_graph[current_node].keys())
        unconnected_neighbors = list(
            filter(
                lambda n: n not in connected_neighbors,
                zx_graph.neighbors(current_node),
            )
        )
        boundary_nodes = explored_leaves + frontier
        if unconnected_neighbors:
            boundary_nodes.append(current_node)
        generating_set_size = sum(len(pauli_graph[n]) for n in boundary_nodes)
        unexplored_neighbors = [n for n in unconnected_neighbors if n not in pauli_graph]
        passthrough_basis = Pauli(1 << (zx_graph.type(current_node) == VertexType.Z))

        # check if each Pauli graph candidate satisfies broadcast and passthrough constraints
        # on the current node and is not a product of previously checked valid Pauli graphs
        valid_graphs, invalid_graphs, syndromes, vector_basis = [], [], [], {}
        for pauli_graph in chain([pauli_graph], pauli_graphs):
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
                if len(vector_basis) == generating_set_size:
                    break

        # try to fix local constraint violations by multiplying with other invalid graphs
        all_one = (1 << len(connected_neighbors)) - 1
        syndrome_basis, basis_graphs = {}, []
        for pauli_graph, syndrome in zip(invalid_graphs, syndromes):
            if len(vector_basis) == generating_set_size:
                break
            for j, target in enumerate((syndrome ^ all_one, syndrome)):  # two valid options
                indices = _solve_linear_system(syndrome_basis, target, update_basis=j == 1)
                if indices is None:
                    if j == 1:
                        basis_graphs.append(pauli_graph)
                    continue
                new_pauli_graph = _multiply_pauli_graphs(
                    [*(basis_graphs[k] for k in indices), pauli_graph]
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
                            ),  # type: ignore (the new graph is always valid so it's always a tuple)
                        )
                    )
                    break

        # enumerate new branches
        pauli_graphs = chain.from_iterable(
            starmap(
                partial(
                    _expand_pauli_graph_to_node,
                    node=current_node,
                    node_basis=passthrough_basis,
                    unconnected_neighbors=unconnected_neighbors,
                    edges_are_hadamard=[
                        is_hadamard(zx_graph, (current_node, n)) for n in unconnected_neighbors
                    ],
                    # always_copy=True,  # can be False if the exploration is BFS
                ),
                valid_graphs,
            )
        )
        pauli_graph = next(pauli_graphs, None)
        if not pauli_graph:  # no valid correlation surface exists on this ZX graph
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

    # eliminate dependent graphs from the final expansion to get a generating set
    return _reform_pauli_graph_generators(
        [pauli_graph, *pauli_graphs],
        lambda pg: pg.signature_at_nodes(
            filter(
                lambda v: zx_graph.vertex_degree(v) == 1,
                zx_graph.vertices(),
            )
        ),
        stabilizer_basis={},
        basis_graphs=[],
        construct_new_graphs=False,
        num_basis_graphs_needed=len(
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
    if in_place:
        normalized_basis = basis
    else:
        normalized_basis = {}
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
