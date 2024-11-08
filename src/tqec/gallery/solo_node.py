"""Build a single node computation graph that represents a logical memory."""

from typing import Literal

from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode
from tqec.position import Position3D


def solo_node_zx_graph(kind: Literal["Z", "X"]) -> ZXGraph:
    """Create a single node ZX graph with the given kind.

    Args:
        kind: The kind of the node, either "Z" or "X".

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance with a single node of the given kind.
    """
    g = ZXGraph(f"Solo {kind} Node")
    g.add_node(ZXNode(Position3D(0, 0, 0), ZXKind(kind)))
    return g


def solo_node_block_graph(support_observable_basis: Literal["Z", "X"]) -> BlockGraph:
    """Create a block graph with a single cube that can support the given
    observable basis.

    A single cube represents a simple logical memory experiment. When the supported observable basis is "Z",
    it corresponds to preserving a logical qubit in the zero state. When the supported observable basis is "X",
    it corresponds to preserving a logical qubit in the plus state.

    Args:
        support_observable_basis: The observable basis that the block graph can support. Either "Z" or "X".

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance with a single cube that can support the
        given observable basis.
    """
    zx_graph = solo_node_zx_graph("X" if support_observable_basis == "Z" else "Z")
    return zx_graph.to_block_graph(f"Logica {support_observable_basis} Memory")
