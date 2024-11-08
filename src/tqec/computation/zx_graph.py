"""ZX graph representation of a logical computation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Generator

import networkx as nx
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D

from tqec.computation._base_graph import ComputationGraph
from tqec.exceptions import TQECException
from tqec.position import Direction3D, Position3D

if TYPE_CHECKING:
    from tqec.computation.block_graph import BlockGraph
    from tqec.computation.correlation import CorrelationSurface


class ZXKind(Enum):
    """The kind of the node in the ZX graph."""

    X = "X"
    """X spider."""
    Y = "Y"
    """Y basis initialization/measurement."""
    Z = "Z"
    """Z spider."""
    P = "PORT"
    """Open port representing the input/output of the graph."""

    def with_zx_flipped(self) -> ZXKind:
        """Return a X/Z kind from a Z/X kind.

        Otherwise, return itself.
        """
        if self == ZXKind.X:
            return ZXKind.Z
        elif self == ZXKind.Z:
            return ZXKind.X
        else:
            return self

    def __str__(self) -> str:
        return self.value

    def __lt__(self, other: ZXKind) -> bool:
        return self.value < other.value


@dataclass(frozen=True, order=True)
class ZXNode:
    """A node in the ZX graph.

    Attributes:
        position: The 3D position of the node.
        kind: The kind of the node.
        label: The label of the node. The label of a port must be non-empty.
            Default to an empty string.
    """

    position: Position3D
    kind: ZXKind
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind == ZXKind.P and not self.label:
            raise TQECException("A port node must have a non-empty label.")

    @property
    def is_port(self) -> bool:
        """Return True if the node is a port."""
        return self.kind == ZXKind.P

    @property
    def is_y_node(self) -> bool:
        """Return True is the node is of ``Y`` kind."""
        return self.kind == ZXKind.Y

    @property
    def is_zx_node(self) -> bool:
        """Return True if the node is of kind ``X`` or ``Z``."""
        return self.kind in [ZXKind.X, ZXKind.Z]

    def with_zx_flipped(self) -> ZXNode:
        """Return a new node with the flipped kind."""
        return ZXNode(self.position, self.kind.with_zx_flipped(), self.label)

    def __str__(self) -> str:
        return f"{self.kind}{self.position}"


@dataclass(frozen=True, order=True)
class ZXEdge:
    """An edge connecting two neighboring nodes in the ZX graph.

    .. warning::
        The attributes ``u`` and ``v`` will be ordered to ensure the position of
        ``u`` is smaller than ``v``.

    Attributes:
        u: The first node of the edge. The position of ``u`` is guaranteed to be
            smaller than ``v``.
        v: The second node of the edge. The position of ``v`` is guaranteed to
            be greater than ``u``.
        has_hadamard: Whether the edge is a Hadamard edge. Default to ``False``.
    """

    u: ZXNode
    v: ZXNode
    has_hadamard: bool = False

    def __post_init__(self) -> None:
        if not self.u.position.is_neighbour(self.v.position):
            raise TQECException("An edge must connect two nearby nodes.")
        # Ensure position of u is less than v
        u, v = self.u, self.v
        if self.u.position > self.v.position:
            object.__setattr__(self, "u", v)
            object.__setattr__(self, "v", u)

    @property
    def direction(self) -> Direction3D:
        """3D direction of the edge."""
        u, v = self.u.position, self.v.position
        if u.x != v.x:
            return Direction3D.X
        if u.y != v.y:
            return Direction3D.Y
        return Direction3D.Z

    def __iter__(self) -> Generator[ZXNode]:
        yield self.u
        yield self.v

    def __str__(self) -> str:
        strs = [str(self.u), str(self.v)]
        if self.has_hadamard:
            strs.insert(1, "H")
        return "-".join(strs)


class ZXGraph(ComputationGraph[ZXNode, ZXEdge]):
    """ZX graph representation of a logical computation.

    This is a restricted form of the ZX graph from the ZX-calculus.
    Currently, the restriction includes:

    1. Every node is positioned at an integer 3D position.
    2. Only nearest-neighbor nodes can be connected by an edge.
    3. X/Z spiders are phase-free.
    4. There are the ``Y`` kind nodes representing the Y basis
       initialization/measurement. It is different from the traditional phased
       X/Z spider representation in ZX-calculus.

    The restrictions are needed because in the end, we need to convert the graph
    to a :py:class:`~tqec.computation.block_graph.BlockGraph` and compile to
    circuits. The block graph poses restrictions on the graph structure. An
    automatic compilation from a simplified or a more general ZX diagram to a
    block graph can relax some of the restrictions. But this is a future work.

    In principle, the rewriting rules from the ZX-calculus can be applied to
    simplify the graph and verify the functionality of the computation. This is
    not implemented yet but might be added in the future.
    """

    def add_edge(
        self,
        u: ZXNode,
        v: ZXNode,
        has_hadamard: bool = False,
    ) -> None:
        """Add an edge to the graph. If the nodes do not exist in the graph,
        the nodes will be created.

        Args:
            u: The first node of the edge.
            v: The second node of the edge.
            has_hadamard: Whether the edge is a Hadamard edge. Default to
                ``False``.

        Raises:
            TQECException: For each node in the edge, if there is already a node
                which is not equal to it at the same position, or the node is a
                port but there is already a different port with the same label
                in the graph.
        """
        self._add_edge_and_nodes_with_checks(u, v, ZXEdge(u, v, has_hadamard))

    def fill_ports(self, fill: Mapping[str, ZXKind] | ZXKind) -> None:
        """Fill the ports at specified positions with nodes of the given kind.

        Args:
            fill: A mapping from the label of the ports to the node kind to fill.
                If a single kind is given, all the ports will be filled with the
                same kind.

        Raises:
            TQECException: if there is no port with the given label or the
                specified kind is ``P``.
        """
        if isinstance(fill, ZXKind):
            fill = {label: fill for label in self._ports}
        for label, kind in fill.items():
            if label not in self._ports:
                raise TQECException(f"There is no port with label {label}.")
            if kind == ZXKind.P:
                raise TQECException("Cannot fill the ports with port kind.")
            pos = self._ports[label]
            fill_node = ZXNode(pos, kind)
            # Overwrite the node at the port position
            self._graph.add_node(pos, **{self._NODE_DATA_KEY: fill_node})
            for edge in self.edges_at(pos):
                self._graph.remove_edge(edge.u.position, edge.v.position)
                other = edge.u if edge.v.position == pos else edge.v
                self._graph.add_edge(
                    other.position,
                    pos,
                    **{
                        self._EDGE_DATA_KEY: ZXEdge(other, fill_node, edge.has_hadamard)
                    },
                )
            # Delete the port label
            self._ports.pop(label)

    def to_block_graph(self, name: str = "") -> BlockGraph:
        """Convert the ZX graph to a
        :py:class:`~tqec.computation.block_graph.BlockGraph`.

        Currently, the conversion respects the explicit 3D structure of the ZX
        graph. And convert node by node, edge by edge. Future work may include
        automatic compilation from a simplified or a more general ZX diagram to
        a block graph implementation.

        To successfully convert a ZX graph to a block graph, the following
        necessary conditions must be satisfied:

        - The ZX graph itself is a valid representation, i.e.
          :py:meth:`~tqec.computation.zx_graph.ZXGraph.check_invariants` does
          not raise an exception.
        - Every nodes in the ZX graph connects to edges at most in two
          directions, i.e. there is no 3D corner node.
        - Y nodes in the ZX graph can only have edges in time direction.

        The conversion process is as follows:

        1. Construct cubes for all the corner nodes in the ZX graph.
        2. Construct pipes connecting ports/Y to ports/Y nodes.
        3. Greedily construct the pipes until no more pipes can be inferred.
        4. If there are still nodes left, then choose orientation for an
           arbitrary node and repeat step 3 and 4 until all nodes are handled or
           conflicts are detected.

        Args:
            zx_graph: The ZX graph to be converted to a block graph.
            name: The name of the new block graph. If None, the name of the ZX
                graph will be used.

        Returns:
            The :py:class:`~tqec.computation.block_graph.BlockGraph` object
            converted from the ZX graph.

        Raises:
            TQECException: If the ZX graph does not satisfy the necessary conditions
                or there are inference conflicts during the conversion.
        """
        from tqec.computation.conversion import (
            convert_zx_graph_to_block_graph,
        )

        return convert_zx_graph_to_block_graph(self, name)

    def find_correration_surfaces(self) -> list[CorrelationSurface]:
        """Find the correlation surfaces in the ZX graph.

        A recursive depth-first search algorithm is used to find the
        correlation surfaces starting from each leaf node.
        """
        from tqec.computation.correlation import find_correlation_surfaces

        return find_correlation_surfaces(self)

    def draw(
        self,
        *,
        figsize: tuple[float, float] = (5, 6),
        title: str | None = None,
        node_size: int = 400,
        hadamard_size: int = 200,
        edge_width: int = 1,
        annotate_ports: bool = True,
    ) -> tuple[Figure, Axes3D]:
        """Plot the :py:class:`~tqec.computation.zx_graph.ZXGraph` using
        matplotlib.

        Args:
            graph: The ZX graph to plot.
            figsize: The figure size. Default is ``(5, 6)``.
            title: The title of the plot. Default to the name of the graph.
            node_size: The size of the node in the plot. Default is ``400``.
            hadamard_size: The size of the Hadamard square in the plot. Default
                is ``200``.
            edge_width: The width of the edge in the plot. Default is ``1``.
            annotate_ports: Whether to annotate the ports if they are present.
                Default is ``True``.

        Returns:
            A tuple of the figure and the axes.
        """
        from tqec.computation.zx_plot import plot_zx_graph

        return plot_zx_graph(
            self,
            figsize=figsize,
            title=title,
            node_size=node_size,
            hadamard_size=hadamard_size,
            edge_width=edge_width,
            annotate_ports=annotate_ports,
        )

    def check_invariants(self) -> None:
        """Check the invariants of a valid ZX graph.

        To represent a valid ZX graph, the graph must fulfill the following
        conditions:

        - The graph is a single connected component.
        - The ports and Y nodes are leaf nodes.

        Raises:
            TQECException: If the invariants are not satisfied.
        """
        if nx.number_connected_components(self._graph) != 1:
            raise TQECException("The ZX graph must be a single connected component.")
        for node in self.nodes:
            if not node.is_zx_node and self.get_degree(node.position) != 1:
                raise TQECException("The port/Y node must be a leaf node.")
