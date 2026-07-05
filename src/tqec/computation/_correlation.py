"""Defines :class:`CorrelationSurface` and functions to find and build them from a ZX graph."""

from __future__ import annotations

import multiprocessing
from collections.abc import (
    Callable,
    Generator,
    Iterable,
    Sequence,
)
from functools import cache
from itertools import (
    accumulate,
    chain,
    combinations,
    pairwise,
    repeat,
    starmap,
)

from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType
from typing_extensions import Self

from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import (
    is_hadamard,
    vertex_type_to_pauli,
    zx_to_pauli,
)
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError


class _CorrelationSurfaceSpace:
    """Bit layout shared by all the correlation surfaces over a graph and its derived subgraphs.

    Each half-edge owns two bits, the X and Z supports of its Pauli operator, at a fixed offset
    (X at the offset, Z above it), so that a whole correlation surface is a single integer and
    the XOR of correlation surfaces and the signatures at fixed nodes, i.e. maskings, run at
    native speed. The two half-edges incident to the two copies of an added boundary vertex
    share a single offset: XORing surfaces supported on the two subgraphs of a cut then
    combines their Pauli operators at the two copies in place, so compatibility across the cut
    is exactly a zero signature at the shared offset.
    """

    __slots__ = ("num_bits", "positions")

    def __init__(self) -> None:
        self.positions: dict[tuple[int, int], int] = {}
        self.num_bits: int = 0

    def _allocate(self) -> int:
        position = self.num_bits
        self.num_bits += 2
        return position

    def register_graph(self, zx_graph: GraphS) -> Self:
        """Allocate the positions of both half-edges of every edge of the graph."""
        positions = self.positions
        for u, v in zx_graph.edges():
            if (u, v) not in positions:
                positions[(u, v)] = self._allocate()
                positions[(v, u)] = self._allocate()
        return self

    def register_boundary_edge(self, inside: int, boundary_vertex: int) -> None:
        """Allocate the positions of a half-edge pair to an added boundary vertex.

        All the half-edges incident to the boundary vertex share a single position, keyed by
        ``(boundary_vertex, boundary_vertex)``, which cannot collide with a real edge.
        """
        positions = self.positions
        if (inside, boundary_vertex) in positions:
            return
        positions[(inside, boundary_vertex)] = self._allocate()
        slot = positions.setdefault((boundary_vertex, boundary_vertex), self._allocate())
        # correct the allocation if the shared slot already existed
        self.num_bits = max(self.num_bits, slot + 2)
        positions[(boundary_vertex, inside)] = slot

    def register_self_loop(self, v: int) -> None:
        """Allocate a position for the self-loop of a single-node surface.

        A single-node correlation surface has no real edge, so its Pauli operator is stored on a
        self-loop half-edge keyed by ``(v, v)``, which cannot collide with a real edge.
        """
        self.positions.setdefault((v, v), self._allocate())

    def dangling_nodes_mask(self, zx_graph: GraphS, nodes: Iterable[int]) -> int:
        """Mask of the single outgoing half-edge of each of the given dangling nodes."""
        positions = self.positions
        mask = 0
        for v in nodes:
            mask |= 3 << positions[(v, next(iter(zx_graph.neighbors(v))))]
        return mask

    def edges_mask(self, zx_graph: GraphS, vertices: Iterable[int]) -> int:
        """Mask of all the half-edges of the graph incident to the given vertices."""
        positions = self.positions
        mask = 0
        for v in vertices:
            for n in zx_graph.neighbors(v):
                mask |= 3 << positions[(v, n)]
        return mask


class _CorrelationSurface:
    """Correlation surface represented as Pauli operators on half-edges.

    The Pauli operators are stored as the X and Z support bits of each half-edge of the
    surface's :class:`_CorrelationSurfaceSpace`. A surface only supports the edges of its
    supporting subgraph, e.g. a single connected component: all the other positions hold zero
    bits, i.e. identities.
    """

    __slots__ = ("bits", "space")

    def __init__(self, space: _CorrelationSurfaceSpace, bits: int = 0) -> None:
        self.space = space
        self.bits = bits

    def add_pauli_to_edge(
        self, edge: tuple[int, int], pauli: Pauli, edge_is_hadamard: bool
    ) -> Self:
        """Add Pauli operators to both ends of the given edge."""
        positions = self.space.positions
        self.bits |= (pauli.value << positions[edge]) | (
            pauli.flipped(edge_is_hadamard).value << positions[edge[::-1]]
        )
        return self

    def to_immutable_public_representation(self, graph: PositionedZX) -> CorrelationSurface:
        """Convert to the public representation of correlation surface.

        The edges of ``graph`` not supported by the surface are identities and do not
        contribute to the public span.
        """
        zx_graph = graph.g
        positions = self.space.positions
        bits = self.bits
        bases = {1: Basis.X, 2: Basis.Z}
        # Edge case: a single-node surface stores its basis on a self-loop half-edge.
        if zx_graph.num_vertices() == 1:
            v = next(iter(zx_graph.vertices()))
            pauli = (bits >> positions[(v, v)]) & 3
            node = ZXNode(graph[v], bases[pauli])
            return CorrelationSurface(frozenset({ZXEdge(node, node)}))
        span: list[ZXEdge] = []
        zx_nodes: dict[tuple[int, Basis], ZXNode] = {}
        for u, v in zx_graph.edges():
            pauli_u = (bits >> positions[(u, v)]) & 3
            pauli_v = (bits >> positions[(v, u)]) & 3
            if not (pauli_u | pauli_v):
                continue
            edge_is_hadamard = is_hadamard(zx_graph, (u, v))
            pos_u, pos_v = graph[u], graph[v]
            for xz_u in (1, 2):
                xz_v = xz_u ^ 3 if edge_is_hadamard else xz_u
                if (pauli_u & xz_u) and (pauli_v & xz_v):
                    basis_u = bases[xz_u]
                    basis_v = bases[xz_v]
                    node_u = zx_nodes.setdefault((u, basis_u), ZXNode(pos_u, basis_u))
                    node_v = zx_nodes.setdefault((v, basis_v), ZXNode(pos_v, basis_v))
                    span.append(ZXEdge.sorted(node_u, node_v))
        return CorrelationSurface(frozenset(span))


def _xor_correlation_surfaces(
    correlation_surfaces: Sequence[_CorrelationSurface],
) -> _CorrelationSurface:
    """XOR multiple correlation surfaces together.

    The input surfaces may be supported on different subgraphs, in which case the result is
    supported on the union of the supports, the uncovered parts being identities.
    """
    bits = 0
    for correlation_surface in correlation_surfaces:
        bits ^= correlation_surface.bits
    return _CorrelationSurface(correlation_surfaces[0].space, bits)


def _partition_graph_from_vertices(
    zx_graph: GraphS, vertices_list: Sequence[set[int]], add_cut_edge_as_boundary_node: bool = False
) -> tuple[list[GraphS], list[tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]]]]]:
    """Create subgraphs from given sets of vertices; optionally add boundary vertices at cuts.

    A cut edge is represented by two BOUNDARY vertices sharing the same new index, below any
    existing vertex index, one in each of the two subgraphs it connects. The boundary vertex is
    recorded as an output vertex of the subgraph coming first in ``vertices_list`` and as an
    input vertex of the other one, mapped to the ``(inside, outside)`` endpoints of the cut
    edge. The type of the cut edge (e.g. Hadamard) is only carried by the output side, so that
    the Pauli operators of two correlation surfaces at the two copies of a boundary vertex are
    directly comparable: they are equal exactly when the surfaces are compatible across the
    cut.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415

    subgraphs = []
    cut_edges_map = {}
    added_vertices_list = []
    next_boundary_vertex = min(0, *zx_graph.vertices()) - 1
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
                        subgraph.add_edge((u, v), zx_graph.edge_type((u, v)))
                elif add_cut_edge_as_boundary_node:
                    key = tuple(sorted((u, v)))
                    if key in cut_edges_map:
                        new_boundary_vertex = cut_edges_map[key]
                        input_vertices[new_boundary_vertex] = (v, u)
                        edge_type = EdgeType.SIMPLE
                    else:
                        new_boundary_vertex = next_boundary_vertex
                        next_boundary_vertex -= 1
                        cut_edges_map[key] = new_boundary_vertex
                        output_vertices[new_boundary_vertex] = (v, u)
                        edge_type = zx_graph.edge_type((u, v))
                    subgraph.add_vertex_indexed(new_boundary_vertex)
                    subgraph.set_type(new_boundary_vertex, VertexType.BOUNDARY)
                    subgraph.add_edge((v, new_boundary_vertex), edge_type)
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


def _reachable_vertices(zx_graph: GraphS, seeds: Iterable[int]) -> set[int]:
    """Collect the vertices of the connected components containing the seed vertices."""
    visited: set[int] = set()
    stack = list(seeds)
    while stack:
        vertex = stack.pop()
        if vertex in visited:
            continue
        visited.add(vertex)
        stack.extend(zx_graph.neighbors(vertex))
    return visited


def _restore_correlation_surface_from_added_vertices(
    correlation_surface: _CorrelationSurface,
    added_vertices: dict[int, tuple[int, int]],
) -> _CorrelationSurface:
    """Restore the correlation surface by recovering the cut edges represented by boundary nodes."""
    positions = correlation_surface.space.positions
    bits = correlation_surface.bits
    for v, (u, w) in added_vertices.items():
        cut_position = positions[(u, v)]
        pauli = (bits >> cut_position) & 3
        if pauli:
            bits ^= (pauli << cut_position) | (pauli << positions[(u, w)])
        bits &= ~(3 << positions[(v, u)])
    correlation_surface.bits = bits
    return correlation_surface


def _cut_edges_as_boundary_pairs(
    zx_graph: GraphS, cut_edges: Iterable[tuple[int, int]]
) -> tuple[GraphS, dict[int, tuple[int, int]]]:
    """Copy the graph, replacing each given edge with a pair of dangling BOUNDARY vertices.

    A cut edge ``(u, v)`` is replaced by two simple edges to two new BOUNDARY vertices with
    negative indices, one dangling from each endpoint. The returned mapping from each boundary
    vertex to the ``(inside, outside)`` endpoints of its cut edge is in the format accepted by
    :func:`_restore_correlation_surface_from_added_vertices`.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415

    cut = {tuple(sorted(edge)) for edge in cut_edges}
    new_graph = GraphS()
    for v in zx_graph.vertices():
        new_graph.add_vertex_indexed(v)
        new_graph.set_type(v, zx_graph.type(v))
        new_graph.set_phase(v, zx_graph.phase(v))
    added_vertices: dict[int, tuple[int, int]] = {}
    next_boundary_vertex = min(0, *zx_graph.vertices()) - 1
    for u, v in zx_graph.edges():
        if tuple(sorted((u, v))) not in cut:
            new_graph.add_edge((u, v), zx_graph.edge_type((u, v)))
            continue
        for inside, outside in ((u, v), (v, u)):
            added_vertices[next_boundary_vertex] = (inside, outside)
            new_graph.add_vertex_indexed(next_boundary_vertex)
            new_graph.set_type(next_boundary_vertex, VertexType.BOUNDARY)
            new_graph.add_edge((inside, next_boundary_vertex))
            next_boundary_vertex -= 1
    return new_graph, added_vertices


def _find_correlation_surfaces_with_vertex_ordering(
    zx_graph: GraphS, vertex_ordering: Sequence[set[int]] | None = None, parallel: bool = True
) -> list[_CorrelationSurface]:
    """Find a generating set of correlation surfaces, optionally sweeping a vertex ordering.

    If ``vertex_ordering`` is ``None`` or empty, the whole graph is searched at once. Otherwise,
    it must partition the graph vertices into disjoint sets, which are swept in the given order:
    the generators of each part are first found independently (in parallel if requested) with
    the cut edges left open, and are then glued onto the generators of the already processed
    parts. The correlation surfaces extending consistently across the cut are exactly the XOR
    combinations of the generators whose Pauli operators match on the cut edges, i.e. the kernel
    of the joint signature at the cut boundary vertices, computed by Gaussian elimination over
    GF(2). After each step, the generators acting as identities on every leaf and every
    unprocessed cut edge are redundant and dropped, which keeps the number of generators carried
    across a cut proportional to the number of dangling nodes instead of the explored graph
    size.

    The returned generators span the same correlation surfaces, up to surfaces acting trivially
    on all the dangling nodes, for any valid ordering: the choice of the ordering only affects
    the performance, with small cuts being cheaper.
    """
    space = _CorrelationSurfaceSpace().register_graph(zx_graph)
    if not vertex_ordering:
        return _find_correlation_surfaces(zx_graph, parallel, space)

    # partition the ZX graph and find correlation surface generators for each part independently
    subgraphs, added_vertices_list = _partition_graph_from_vertices(zx_graph, vertex_ordering, True)
    for part_added_vertices in added_vertices_list:
        for added_vertices in part_added_vertices:
            for boundary_vertex, (inside, _) in added_vertices.items():
                space.register_boundary_edge(inside, boundary_vertex)
    if parallel and len(subgraphs) > 1:
        with multiprocessing.Pool() as pool:
            part_surfaces_list = pool.starmap(
                _find_correlation_surfaces, ((subgraph, False, space) for subgraph in subgraphs)
            )
    else:
        part_surfaces_list = [
            _find_correlation_surfaces(subgraph, space=space) for subgraph in subgraphs
        ]

    surfaces: list[_CorrelationSurface] = []
    # half-edges at the leaves and at the unprocessed cut edges among the processed parts
    dangling_mask = 0
    for subgraph, part_surfaces, (input_vertices, _) in zip(
        subgraphs, part_surfaces_list, added_vertices_list
    ):
        surfaces.extend(part_surfaces)
        input_mask = 0
        for boundary_vertex, (inside, _) in input_vertices.items():
            input_mask |= 3 << space.positions[(boundary_vertex, inside)]
        if input_mask:
            # Glue the part onto the previously processed parts: keep the kernel of the joint
            # signature at the boundary vertices, whose elements have matching paulis at the
            # two copies of each boundary vertex.
            surfaces = _reform_correlation_surface_generators(
                surfaces,
                lambda cs: cs.bits & input_mask,
                stabilizer_basis={},
                basis_surfaces=[],
            )[1]
        dangling_mask |= space.dangling_nodes_mask(
            subgraph, (v for v in subgraph.vertices() if subgraph.vertex_degree(v) == 1)
        )
        dangling_mask &= ~input_mask
        # A generator whose signature at the dangling nodes depends on the other generators'
        # signatures only differs from their XOR by a surface staying trivial on all the
        # unprocessed parts and leaves, so it is redundant and dropped.
        surfaces = _reform_correlation_surface_generators(
            surfaces,
            lambda cs: cs.bits & dangling_mask,
            stabilizer_basis={},
            basis_surfaces=[],
            construct_new_surfaces=False,
        )[0]

    # restore the cut edges represented by the pairs of boundary vertices
    for correlation_surface in surfaces:
        for added_vertices in chain.from_iterable(added_vertices_list):
            _restore_correlation_surface_from_added_vertices(correlation_surface, added_vertices)

    # Match the per-component normalization of the direct search: reform the generators
    # supported on the components with open leaves, keeping the other generators as they are.
    open_leaves = [
        v
        for v in zx_graph.vertices()
        if zx_graph.vertex_degree(v) == 1 and zx_to_pauli(zx_graph, v) is Pauli.I
    ]
    if open_leaves and surfaces:
        open_components_mask = space.edges_mask(
            zx_graph, _reachable_vertices(zx_graph, open_leaves)
        )
        normalized_surfaces = _normalize_correlation_surfaces_at_open_leaves(
            (cs for cs in surfaces if cs.bits & open_components_mask),
            space.dangling_nodes_mask(zx_graph, open_leaves),
        )
        surfaces = [
            cs for cs in surfaces if not cs.bits & open_components_mask
        ] + normalized_surfaces
    return surfaces


def _find_correlation_surface_containing(
    zx_graph: GraphS,
    half_edge_paulis: dict[tuple[int, int], Pauli],
    vertex_ordering: Sequence[set[int]] | None = None,
    parallel: bool = True,
) -> _CorrelationSurface | None:
    """Find a correlation surface with exactly the given Pauli operators on the given edges.

    ``half_edge_paulis`` maps each constrained edge, in both orientations, to the Pauli
    operator on the half-edge incident to the first vertex; the two orientations must be
    consistent with the edge type. Each constrained edge is cut into a pair of dangling
    boundary vertices, so the surface search keeps the generators' resolution at the
    constrained edges, including surfaces acting trivially on all the leaves of the original
    graph, e.g. broadcasts around a cycle. A combination of generators with the required Pauli
    operators at the boundary vertices, which is a valid correlation surface with exactly the
    required operators on the constrained edges once the cut edges are spliced back, is then
    found by Gaussian elimination over GF(2). Returns ``None`` if the requirements cannot be
    satisfied, i.e. the required Paulis are outside the span of the generators' signatures.
    """
    cut_graph, added_vertices = _cut_edges_as_boundary_pairs(zx_graph, half_edge_paulis)
    if vertex_ordering is not None:
        # keep the partition valid by assigning each boundary vertex to its endpoint's part
        vertex_ordering = [
            part | {b for b, (inside, _) in added_vertices.items() if inside in part}
            for part in vertex_ordering
        ]
    correlation_surfaces = _find_correlation_surfaces_with_vertex_ordering(
        cut_graph, vertex_ordering, parallel
    )
    if not correlation_surfaces:
        return None
    # also allocate the positions of the cut edges, which are restored in the solution
    space = correlation_surfaces[0].space.register_graph(zx_graph)
    boundary_mask = 0
    target = 0
    for boundary_vertex, edge in added_vertices.items():
        position = space.positions[(boundary_vertex, edge[0])]
        boundary_mask |= 3 << position
        target |= half_edge_paulis[edge].value << position
    stabilizer_basis: dict[int, tuple[int, int]] = {}
    basis_surfaces = _reform_correlation_surface_generators(
        correlation_surfaces,
        lambda cs: cs.bits & boundary_mask,
        stabilizer_basis,
        [],
        construct_new_surfaces=False,
    )[0]
    indices = _solve_linear_system(stabilizer_basis, target, update_basis=False)
    if indices is None:
        return None
    return _restore_correlation_surface_from_added_vertices(
        _xor_correlation_surfaces([basis_surfaces[k] for k in indices]), added_vertices
    )


def _find_correlation_surfaces(
    zx_graph: GraphS, parallel: bool = True, space: _CorrelationSurfaceSpace | None = None
) -> list[_CorrelationSurface]:
    """Find a generating set of correlation surfaces of the graph.

    The generators of each connected component are found independently, possibly in parallel,
    and concatenated: a generator only covers its own component and implicitly extends to the
    whole graph with identities, so the products of generators from different components do not
    need to be enumerated.
    """
    if space is None:
        space = _CorrelationSurfaceSpace().register_graph(zx_graph)
    components = [
        (
            component,
            min(v for v in component.vertices() if component.vertex_degree(v) == 1),
            space,
        )
        for component in _partition_graph_into_connected_components(zx_graph)
    ]
    if parallel and len(components) > 1:
        with multiprocessing.Pool() as pool:
            correlation_surfaces = pool.starmap(_find_correlation_surfaces_from_leaf, components)
    else:
        correlation_surfaces = list(starmap(_find_correlation_surfaces_from_leaf, components))
    return list(chain.from_iterable(correlation_surfaces))


def _find_correlation_surfaces_from_leaf(
    zx_graph: GraphS, leaf: int, space: _CorrelationSurfaceSpace
) -> list[_CorrelationSurface]:
    """Find the correlation surface generators satisfying the closed ports."""
    correlation_surfaces = _find_correlation_surface_generating_set_from_leaf(zx_graph, leaf, space)

    leaves = {pauli: [] for pauli in Pauli.iter_ixzy()}
    for v in filter(
        lambda v: zx_graph.vertex_degree(v) == 1,
        zx_graph.vertices(),
    ):
        leaves[zx_to_pauli(zx_graph, v).flipped()].append(v)
    open_leaves = leaves.pop(Pauli.I)

    # The signature of the closed port constraints: a violating Pauli operator at a leaf that
    # only supports {I, X} ({I, Z}) has its Z (X) bit set, and one that only supports {I, Y}
    # has X and Z bits of different values.
    violation_mask = 0
    y_leaf_positions = []
    for allowed_pauli, closed_leaves in leaves.items():
        for v in closed_leaves:
            position = space.positions[(v, next(iter(zx_graph.neighbors(v))))]
            if allowed_pauli is Pauli.Y:
                y_leaf_positions.append(position)
            else:
                violation_mask |= (allowed_pauli.value ^ 3) << position

    if violation_mask or y_leaf_positions:

        def closed_ports_signature(cs: _CorrelationSurface) -> int:
            signature = cs.bits & violation_mask
            for position in y_leaf_positions:
                signature = (signature << 1) | (
                    ((cs.bits >> position) ^ (cs.bits >> (position + 1))) & 1
                )
            return signature

        correlation_surfaces = _reform_correlation_surface_generators(
            correlation_surfaces,
            closed_ports_signature,
            stabilizer_basis={},
            basis_surfaces=[],
        )[1]

    if open_leaves:
        correlation_surfaces = _normalize_correlation_surfaces_at_open_leaves(
            correlation_surfaces, space.dangling_nodes_mask(zx_graph, open_leaves)
        )

    return correlation_surfaces


def _reform_correlation_surface_generators(
    correlation_surfaces: Iterable[_CorrelationSurface],
    signature_func: Callable[[_CorrelationSurface], int],
    stabilizer_basis: dict[int, tuple[int, int]],
    basis_surfaces: Sequence[_CorrelationSurface],
    construct_new_surfaces: bool = True,
    num_new_surfaces_needed: int | None = None,
    num_basis_surfaces_needed: int | None = None,
) -> tuple[list[_CorrelationSurface], list[_CorrelationSurface]]:
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


def _normalize_correlation_surfaces_at_open_leaves(
    correlation_surfaces: Iterable[_CorrelationSurface],
    open_leaves_mask: int,
) -> list[_CorrelationSurface]:
    """Reform the generators into a normalized basis of the signatures at the open leaves.

    The reformed generators have distinct leading Pauli supports at the open leaves when
    possible, which minimizes the number of Y-terminating correlation surfaces. A generator
    whose signature at the open leaves depends on the other generators' signatures does not
    provide new correlations between the open leaves and is dropped.
    """
    stabilizer_basis: dict[int, tuple[int, int]] = {}
    basis_surfaces = _reform_correlation_surface_generators(
        correlation_surfaces,
        lambda cs: cs.bits & open_leaves_mask,
        stabilizer_basis,
        [],
        construct_new_surfaces=False,
    )[0]
    return [
        _xor_correlation_surfaces([basis_surfaces[i] for i in indices])
        if len(indices := _int_to_bit_indices(mask)) > 1
        else basis_surfaces[indices[0]]
        for _, mask in _normalize_basis(stabilizer_basis).values()
    ]


# Enumerating all local configurations is exponential in the node degree, so it is only worth
# it below this many unconnected neighbors, where the more diverse candidates tend to saturate
# the Gaussian elimination with fewer scanned candidates. All the spiders of a block graph are
# below the threshold, which caps the enumeration at high-degree spiders, e.g. from imported
# ZX diagrams, where a generating set of the local configurations is enumerated instead.
_GENERATE_ALL_MAX_NEIGHBORS = 5


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


def _expand_correlation_surfaces_to_node(
    space: _CorrelationSurfaceSpace,
    valid_surfaces: list[tuple[_CorrelationSurface, Pauli, bool]],
    node_basis: Pauli,
    unconnected_positions: list[tuple[int, int, bool]],
) -> Generator[_CorrelationSurface, None]:
    """Expand to a generating set of correlation surfaces for the new node.

    Every valid surface is combined with the valid local Pauli configurations on the
    unconnected half-edges compatible with its broadcast Pauli and passthrough parity, given as
    XOR deltas in the bit space.
    """
    generate_all = len(unconnected_positions) <= _GENERATE_ALL_MAX_NEIGHBORS
    deltas_cache: dict[tuple[Pauli, bool], list[int]] = {}
    for surface, broadcast_pauli, passthrough_parity in valid_surfaces:
        deltas = deltas_cache.get((broadcast_pauli, passthrough_parity))
        if deltas is None:
            deltas = [
                sum(
                    (pauli.value << position_out)
                    | (pauli.flipped(edge_is_hadamard).value << position_in)
                    for pauli, (position_out, position_in, edge_is_hadamard) in zip(
                        out_paulis, unconnected_positions
                    )
                )
                for out_paulis in _generate_valid_local_paulis(
                    node_basis,
                    broadcast_pauli,
                    passthrough_parity,
                    len(unconnected_positions),
                    generate_all=generate_all,
                )
            ]
            deltas_cache[(broadcast_pauli, passthrough_parity)] = deltas
        for delta in deltas:
            yield _CorrelationSurface(space, surface.bits ^ delta)


def _find_correlation_surface_generating_set_from_leaf(
    zx_graph: GraphS, leaf: int, space: _CorrelationSurfaceSpace
) -> list[_CorrelationSurface]:
    """Find a generating set of correlation surfaces assuming all ports are open."""
    positions = space.positions
    neighbor: int = next(iter(zx_graph.neighbors(leaf)))
    correlation_surfaces = (
        _CorrelationSurface(space).add_pauli_to_edge(
            (leaf, neighbor), pauli, is_hadamard(zx_graph, (leaf, neighbor))
        )
        for pauli in Pauli.iter_xz()
    )
    if zx_graph.vertex_degree(neighbor) == 1:
        # edge case, make sure no leaf node will be in the frontier
        return list(correlation_surfaces)
    frontier = [neighbor]
    explored_leaves = [leaf]
    # the neighbors with an assigned half-edge at each reached node; the exploration state is
    # shared by all the candidate surfaces
    assigned_neighbors: dict[int, list[int]] = {leaf: [neighbor], neighbor: [leaf]}
    # Each candidate surface is serialized once per step, so its Pauli operators at scattered
    # positions are byte lookups instead of shifts of the whole surface integer. The two bits
    # of a Pauli operator never straddle a byte boundary because the positions are even.
    num_bytes = (space.num_bits + 7) >> 3
    correlation_surface = next(correlation_surfaces)

    while frontier:
        # Explore a frontier node whose edges are all assigned first: it closes cycles and
        # shrinks the boundary without assigning new edges, which keeps the signatures and the
        # generating sets small. The other nodes are explored in FIFO order.
        current_node = frontier.pop(
            next(
                (
                    i
                    for i, n in enumerate(frontier)
                    if zx_graph.vertex_degree(n) == len(assigned_neighbors[n])
                ),
                0,
            )
        )
        connected_neighbors = assigned_neighbors[current_node]
        connected_set = set(connected_neighbors)
        unconnected_neighbors = [
            n for n in zx_graph.neighbors(current_node) if n not in connected_set
        ]
        passthrough_basis = zx_to_pauli(zx_graph, current_node)
        has_unconnected = bool(unconnected_neighbors)

        # The signatures at the assigned half-edges of the boundary (dangling and frontier)
        # nodes are extracted into dense integers, so the Gaussian elimination runs on small
        # integers however wide the surfaces have grown.
        boundary_nodes = chain(
            explored_leaves, frontier, (current_node,) if has_unconnected else ()
        )
        signature_positions = [
            positions[(n, m)] for n in boundary_nodes for m in assigned_neighbors[n]
        ]
        generating_set_size = len(signature_positions)

        def boundary_signature(data: bytes) -> int:
            signature = 0
            shift = 0
            for position in signature_positions:
                signature |= ((data[position >> 3] >> (position & 7)) & 3) << shift
                shift += 2
            return signature

        # compact masks for the broadcast and passthrough rules at the current node
        passthrough_shift = 0 if passthrough_basis is Pauli.X else 1
        broadcast_shift = 1 - passthrough_shift
        connected_positions = [positions[(current_node, n)] for n in connected_neighbors]
        passthrough_mask = sum(
            1 << (2 * i + passthrough_shift) for i in range(len(connected_positions))
        )
        broadcast_mask = passthrough_mask >> passthrough_shift << broadcast_shift
        broadcast_basis = passthrough_basis.flipped()

        def validate_node(data: bytes) -> int | tuple[Pauli, bool]:
            """Return the broadcast Pauli and passthrough parity if valid, else the syndrome."""
            paulis = 0
            shift = 0
            for position in connected_positions:
                paulis |= ((data[position >> 3] >> (position & 7)) & 3) << shift
                shift += 2
            broadcast_bits = paulis & broadcast_mask
            passthrough_parity = (paulis & passthrough_mask).bit_count() & 1
            if not broadcast_bits:
                broadcast_pauli = Pauli.I
            elif broadcast_bits == broadcast_mask:
                broadcast_pauli = broadcast_basis
            else:  # invalid broadcast
                broadcast_pauli = None
            if broadcast_pauli is not None and (has_unconnected or not passthrough_parity):
                return broadcast_pauli, bool(passthrough_parity)
            # The syndrome holds the broadcast violation bit of each connected edge, at one bit
            # every two, and the passthrough parity above them when it must be even.
            syndrome = broadcast_bits >> broadcast_shift
            if not has_unconnected:
                syndrome |= passthrough_parity << (2 * len(connected_positions))
            return syndrome

        # check if each correlation surface candidate satisfies broadcast and passthrough rules
        # on the current node and is not a product of previously checked valid correlation surfaces
        valid_surfaces, invalid_surfaces, syndromes, vector_basis = [], [], [], {}
        for correlation_surface in chain([correlation_surface], correlation_surfaces):
            data = correlation_surface.bits.to_bytes(num_bytes, "little")
            constraint_check = validate_node(data)
            if isinstance(constraint_check, int):  # invalid
                invalid_surfaces.append(correlation_surface)
                syndromes.append(constraint_check)
                continue
            if (
                _solve_linear_system(vector_basis, boundary_signature(data)) is None
            ):  # new independent surface
                valid_surfaces.append((correlation_surface, *constraint_check))
                if len(vector_basis) == generating_set_size:
                    break

        # try to fix local constraint violations by XORing with other invalid surfaces
        all_one = broadcast_mask >> broadcast_shift  # flips every edge's broadcast bit
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
                new_data = new_correlation_surface.bits.to_bytes(num_bytes, "little")
                if _solve_linear_system(vector_basis, boundary_signature(new_data)) is None:
                    valid_surfaces.append(
                        (
                            new_correlation_surface,
                            *validate_node(new_data),  # type: ignore (the new surface is always valid so it's always a tuple)
                        )
                    )
                    break

        # enumerate new branches from the valid surfaces; the arguments are bound at the call,
        # so the lazily consumed generator is unaffected by the next iterations of the loop
        unconnected_positions = [
            (
                positions[(current_node, n)],
                positions[(n, current_node)],
                is_hadamard(zx_graph, (current_node, n)),
            )
            for n in unconnected_neighbors
        ]
        correlation_surfaces = _expand_correlation_surfaces_to_node(
            space, valid_surfaces, passthrough_basis, unconnected_positions
        )
        correlation_surface = next(correlation_surfaces, None)
        if correlation_surface is None:  # no valid correlation surface exists on this ZX graph
            return []

        # update the shared exploration state with the newly assigned half-edges
        connected_neighbors.extend(unconnected_neighbors)
        for n in unconnected_neighbors:
            if n in assigned_neighbors:  # a boundary node reached through another edge
                assigned_neighbors[n].append(current_node)
                continue
            assigned_neighbors[n] = [current_node]
            if zx_graph.vertex_degree(n) == 1:
                explored_leaves.append(n)
            else:
                frontier.append(n)

    # eliminate dependent surfaces from the final expansion to get a generating set
    all_leaves = [v for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1]
    all_leaves_mask = space.dangling_nodes_mask(zx_graph, all_leaves)
    return _reform_correlation_surface_generators(
        [correlation_surface, *correlation_surfaces],
        lambda cs: cs.bits & all_leaves_mask,
        stabilizer_basis={},
        basis_surfaces=[],
        construct_new_surfaces=False,
        num_basis_surfaces_needed=len(all_leaves),
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
