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
    from pyzx.pauliweb import PauliWeb

    from tqec.computation._correlation import _CorrelationSurface
    from tqec.computation.block_graph import BlockGraph
    from tqec.interop.pyzx.positioned import PositionedZX


class ZXNode(NamedTuple):
    """Represent a node in the PositionedZX graph spanned by the correlation surface.

    Correlation surface is represented by a set of edges in the ZX graph. Each edge
    consists of two nodes. The node position refers to the 3D position in the graph
    and the basis represents the Pauli operator on the half edge incident to the node.

    Attributes:
        position: The position of the node in 3D space.
        basis: The Pauli operator on the half edge incident to the node.

    """

    position: Position3D
    basis: Basis


class ZXEdge(NamedTuple):
    """Represent an edge in the PositionedZX graph spanned by the correlation surface.

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
        return self.u.position == self.v.position

    @property
    def has_hadamard(self) -> bool:
        """Whether the edge has a hadamard effect."""
        return self.u.basis is not self.v.basis

    def get_basis(self, position: Position3D) -> Basis:
        """Get the basis of the half edge incident to the given position."""
        match position:
            case self.u.position:
                return self.u.basis
            case self.v.position:
                return self.v.basis
            case _:
                raise TQECError(f"Position {position} is not incident to the edge {self}.")


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
    def _graph_view(
        self,
    ) -> tuple[dict[Position3D, dict[Position3D, list[ZXEdge]]], dict[Position3D, set[Basis]]]:
        """Internal index mapping positions to active bases and incident edges."""
        edges, bases = {}, {}
        for edge in self.span:
            u, v = edge.u.position, edge.v.position
            edges.setdefault(u, {}).setdefault(v, []).append(edge)
            edges.setdefault(v, {}).setdefault(u, []).append(edge)
            bases.setdefault(u, set()).add(edge.u.basis)
            bases.setdefault(v, set()).add(edge.v.basis)
        return edges, bases

    def bases_at(self, position: Position3D) -> set[Basis]:
        """Get the bases of the surfaces present at the position."""
        return self._graph_view[1][position]

    def to_pauli_web(self, g: PositionedZX) -> PauliWeb[int, tuple[int, int]]:
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
    def from_pauli_web(
        pauli_web: PauliWeb[int, tuple[int, int]], g: PositionedZX
    ) -> CorrelationSurface:
        """Create a correlation surface from a Pauli web."""
        # Avoid pulling pyzx when importing that module.
        from tqec.interop.pyzx.correlation import pauli_web_to_correlation_surface  # noqa: PLC0415

        return pauli_web_to_correlation_surface(pauli_web, g)

    @property
    def is_single_node(self) -> bool:
        """Whether the correlation surface contains only a single node.

        This is an edge case where the ZX graph only contains a single node. The span of the
        correlation surface is a self-loop edge at the node.

        """
        return len(self.span) == 1 and next(iter(self.span)).is_self_loop

    @property
    def positions(self) -> set[Position3D]:
        """Return the set of positions in the correlation surface."""
        return set(self._graph_view[0].keys())

    def edges_at(self, position: Position3D) -> set[ZXEdge]:
        """Return the set of edges incident to the position in the correlation surface."""
        return set(chain.from_iterable(self._graph_view[0][position].values()))

    def external_stabilizer(self, io_ports: list[Position3D]) -> str:
        """Get the Pauli operator supported on the given input/output ports.

        Args:
            io_ports: The list of input/output ports to consider.

        Returns:
            The Pauli operator supported on the given ports.

        """
        assert all(isinstance(port, Position3D) for port in io_ports)
        return "".join(
            str(Pauli.from_basis_set(self._graph_view[1].get(port, set()))) for port in io_ports
        )

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
        return self.external_stabilizer(supports)

    @cached_property
    def area(self) -> int:
        """Return the area of the correlation surface.

        The area of the correlation surface is the number of nodes it spans. A X node and a Z node
        with the same id are counted as two nodes.

        """
        span_nodes = {node for edge in self.span for node in edge}
        return len(span_nodes)

    def shift_by(self, dx: int = 0, dy: int = 0, dz: int = 0) -> CorrelationSurface:
        """Shift a copy of ``self`` by the given offset in the x, y, z directions and return it.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
            dz: The offset in the z direction.

        Returns:
            A new correlation surface with the shifted positions. The new correlation surface will
            share no data with the original correlation surface.

        """
        # to avoid instantiating unnecessary copies of identical nodes
        nodes: dict[ZXNode, ZXNode] = {}
        for position in self.positions:
            new_position = Position3D(
                position.x + dx,
                position.y + dy,
                position.z + dz,
            )
            for basis in self.bases_at(position):
                old_node = ZXNode(position, basis)
                new_node = ZXNode(new_position, basis)
                nodes[old_node] = new_node
        return CorrelationSurface(
            frozenset({ZXEdge.sorted(nodes[edge.u], nodes[edge.v]) for edge in self.span})
        )

    def __xor__(self, other: CorrelationSurface) -> CorrelationSurface:
        return CorrelationSurface(self.span.symmetric_difference(other.span))

    def _to_mutable_graph_representation(self, graph: PositionedZX) -> _CorrelationSurface:
        """Convert to the internal mutable representation."""
        # Avoid pulling pyzx when importing that module.
        from tqec.computation._correlation import _CorrelationSurface  # noqa: PLC0415
        from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

        p2v = graph.p2v
        zx_graph = graph.g
        surface = _CorrelationSurface()
        for pos_u, edges in self._graph_view[0].items():
            u = p2v[pos_u]
            for pos_v, edge in edges.items():
                v = p2v[pos_v]
                surface._add_pauli_to_edge(
                    (u, v),
                    reduce(xor, (e.get_basis(pos_u).to_pauli() for e in edge)),
                    is_hadamard(zx_graph, (u, v)),
                )
        for u, v in zx_graph.edges():
            if u not in surface or v not in surface[u]:
                surface._add_pauli_to_edge((u, v), Pauli.I, False)
        return surface


def find_correlation_surfaces(
    graph: PositionedZX,
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
    3. Reform the generators so that they satisfy the closed ports (non-BOUNDARY leaf nodes).
    4. Reform the generators so that the number of Y-terminating correlation surfaces is minimized.
    5. Combine the generators from all connected components.

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
        graph: The PositionedZX graph to find the correlation surfaces.
        vertex_ordering: A reserved argument for an unfinished feature. Should not be used at this
            moment.
        parallel: Whether to use multiprocessing to speed up the computation. Only applies to
            embarrassingly parallel parts of the algorithm. Default is `False`.

    Returns:
        A list of `CorrelationSurface` in the graph.

    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _find_correlation_surfaces_with_vertex_ordering,
    )
    from tqec.interop.pyzx.utils import zx_to_basis  # noqa: PLC0415

    if vertex_ordering is not None:
        raise NotImplementedError(
            "The `vertex_ordering` argument is reserved for an unfinished feature and should not"
            " be used at this moment."
        )
    zx_graph = graph.g
    _check_spiders_are_supported(zx_graph)
    # Edge case: single node graph
    if zx_graph.num_vertices() == 1:
        v = next(iter(zx_graph.vertices()))
        node = ZXNode(graph[v], zx_to_basis(zx_graph, v).flipped())
        return [CorrelationSurface(frozenset({ZXEdge(node, node)}))]

    leaves = {v for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1}
    if not leaves:
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )

    # sort the correlation surfaces by area
    return sorted(
        (
            cs._to_immutable_public_representation(graph)
            for cs in _find_correlation_surfaces_with_vertex_ordering(
                zx_graph, vertex_ordering, parallel
            )
        ),
        key=lambda x: sorted(x.span),
    )


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
