"""Base class for graph data structures representing logical computations."""

from __future__ import annotations

from typing import Generic, TypeVar, Protocol, cast

import networkx as nx

from tqec.exceptions import TQECException
from tqec.position import Position3D


class ComputationNode(Protocol):
    @property
    def position(self) -> Position3D: ...

    @property
    def label(self) -> str: ...

    @property
    def is_port(self) -> bool:
        """Check if the node is a port."""
        ...


_NODE = TypeVar("_NODE", bound=ComputationNode)
_EDGE = TypeVar("_EDGE")


class ComputationGraph(Generic[_NODE, _EDGE]):
    """Base class for graph data structures representing a logical
    computation."""

    _NODE_DATA_KEY: str = "tqec_node_data"
    _EDGE_DATA_KEY: str = "tqec_edge_data"

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._graph: nx.Graph[Position3D] = nx.Graph()
        self._ports: dict[str, Position3D] = {}

    @property
    def name(self) -> str:
        """Name of the graph."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def num_nodes(self) -> int:
        """Number of nodes in the graph."""
        return self._graph.number_of_nodes()

    @property
    def num_edges(self) -> int:
        """Number of edges in the graph."""
        return self._graph.number_of_edges()

    @property
    def num_ports(self) -> int:
        """Number of ports in the graph."""
        return len(self._ports)

    @property
    def nodes(self) -> list[_NODE]:
        """The list of nodes in the graph."""
        return [data[self._NODE_DATA_KEY] for _, data in self._graph.nodes(data=True)]

    @property
    def edges(self) -> list[_EDGE]:
        """The list of edges in the graph."""
        return [
            data[self._EDGE_DATA_KEY] for _, _, data in self._graph.edges(data=True)
        ]

    @property
    def ports(self) -> dict[str, Position3D]:
        """Mapping from port labels to their positions.

        A port is a virtual node with unique label that represents the
        input/output of the computation.
        """
        return self._ports

    def get_degree(self, position: Position3D) -> int:
        """Get the degree of a node in the graph, i.e. the number of edges
        incident to it."""
        return self._graph.degree(position)  # type: ignore

    @property
    def leaf_nodes(self) -> list[_NODE]:
        """Get the leaf nodes of the graph, i.e. the nodes with degree 1."""
        return [node for node in self.nodes if self.get_degree(node.position) == 1]

    def _check_node_conflict(self, node: _NODE) -> None:
        """Check whether a new node can be added to the graph without conflict.

        The following circumstances are considered conflicts:

            - There is already a node which is not equal to this one at the same position.
            - The node is a port but there is already a different port with the same label
                in the graph.
        """
        position = node.position
        if position in self:
            if self[position] == node:
                return
            raise TQECException(
                f"The graph already has a different node {self[position]} at this position."
            )
        if node.is_port and node.label in self._ports:
            raise TQECException(
                f"There is already a different port with label {node.label} in the graph."
            )

    def add_node(self, node: _NODE, check_conflict: bool = True) -> None:
        """Add a node to the graph.

        Args:
            node: The node to add to the graph.
            check_conflict: Whether to check for conflicts before adding the node. If set to
                True, either one of the following two circumstances will raise an exception:

                1. There is already a node which is not equal to this one at the same position.
                2. The node is a port but there is already a different port with the same label
                   in the graph.

                Otherwise, an existing node at the same position will be overwritten. Defaults to
                True.

        Raises:
            TQECException: If ``check_conflict`` is True and there is a conflict when adding the
                node.
        """
        if check_conflict:
            self._check_node_conflict(node)
        self._graph.add_node(node.position, **{self._NODE_DATA_KEY: node})
        if node.is_port:
            self._ports[node.label] = node.position

    def _add_edge_and_nodes_with_checks(self, u: _NODE, v: _NODE, edge: _EDGE) -> None:
        """Add an edge to the graph with nodes and edge all specified."""
        # Check before adding the nodes to avoid rolling back the changes
        self._check_node_conflict(u)
        self._check_node_conflict(v)
        self.add_node(u, check_conflict=False)
        self.add_node(v, check_conflict=False)
        self._graph.add_edge(u.position, v.position, **{self._EDGE_DATA_KEY: edge})

    def has_edge_between(self, pos1: Position3D, pos2: Position3D) -> bool:
        """Check if there is an edge between two positions.

        Args:
            pos1: The first endpoint position.
            pos2: The second endpoint position.

        Returns:
            True if there is an edge between the two positions, False otherwise.
        """
        return self._graph.has_edge(pos1, pos2)

    def get_edge(self, pos1: Position3D, pos2: Position3D) -> _EDGE:
        """Get the edge by its endpoint positions. If there is no edge between
        the given positions, an exception will be raised.

        Args:
            pos1: The first endpoint position.
            pos2: The second endpoint position.

        Returns:
            The edge between the two positions.

        Raises:
            TQECException: If there is no edge between the given positions.
        """
        if not self.has_edge_between(pos1, pos2):
            raise TQECException("No edge between the given positions in the graph.")
        return cast(_EDGE, self._graph.edges[pos1, pos2][self._EDGE_DATA_KEY])

    def edges_at(self, position: Position3D) -> list[_EDGE]:
        """Get the edges incident to a position."""
        if position not in self:
            return []
        return [
            cast(_EDGE, data[self._EDGE_DATA_KEY])
            for _, _, data in self._graph.edges(position, data=True)
        ]

    def __contains__(self, position: Position3D) -> bool:
        return position in self._graph

    def __getitem__(self, position: Position3D) -> _NODE:
        return cast(_NODE, self._graph.nodes[position][self._NODE_DATA_KEY])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            nx.utils.graphs_equal(self._graph, other._graph)  # type: ignore
            and self._ports == other._ports
        )
