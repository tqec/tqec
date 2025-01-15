"""Build computation that rotating boundary types by moving logical qubit in spacetime."""

from typing import Literal, cast

from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXKind, ZXGraph, ZXNode
from tqec.position import Position3D


def move_rotation_zx_graph(port_kind: Literal["Z", "X", "OPEN"]) -> ZXGraph:
    """Create a ZX graph for moving and rotating the spatial boundaries of a logical qubit.

    Args:
        port_kind: The node kind to fill the two ports of the graph. It can be
            either "Z", "X", or "OPEN". If "OPEN", the ports are left open.
            Otherwise, the ports are filled with the given node kind.

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance representing the
        move-rotation operation.
    """
    g = ZXGraph("Move Rotation")
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, "In"),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(0, 1, 1), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(0, 1, 1), ZXKind.X),
        ZXNode(Position3D(1, 1, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 1), ZXKind.Z),
        ZXNode(Position3D(1, 1, 2), ZXKind.P, "Out"),
    )
    if port_kind != "OPEN":
        g.fill_ports(ZXKind(port_kind))

    return g


def move_rotation_block_graph(
    support_observable_basis: Literal["Z", "X", "BOTH"],
) -> BlockGraph:
    """Create a block graph for moving and rotating the spatial boundaries of a logical qubit.

    Args:
        support_observable_basis: The observable basis that the block graph can support.
            It can be either "Z", "X", or "BOTH". Note that a cube at the port can only
            support the observable basis opposite to the cube. If "Z", the two ports of
            the block graph are filled with X basis cubes. If "X", the two ports are
            filled with Z basis cubes. If "BOTH", the two ports are left open.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the move-rotation operation.
    """
    if support_observable_basis == "BOTH":
        port_kind = "OPEN"
    elif support_observable_basis == "Z":
        port_kind = "X"
    else:
        port_kind = "Z"
    zx_graph = move_rotation_zx_graph(cast(Literal["Z", "X", "OPEN"], port_kind))
    return zx_graph.to_block_graph("Move Rotation")
