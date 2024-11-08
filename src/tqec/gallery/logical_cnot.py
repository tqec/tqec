"""Build computation graphs that represent a logical CNOT gate."""

from typing import Literal, cast
from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXKind, ZXGraph, ZXNode
from tqec.position import Position3D


def logical_cnot_zx_graph(port_kind: Literal["Z", "X", "OPEN"]) -> ZXGraph:
    """Create a ZX graph for the logical CNOT gate.

    Args:
        port_kind: The node kind to fill the four ports of the logical CNOT
            gate. It can be either "Z", "X", or "OPEN". If "OPEN", the ports are
            left open. Otherwise, the ports are filled with the given node kind.

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance representing the
        logical CNOT gate.
    """
    if port_kind != "OPEN":
        name = f"Logical CNOT with {port_kind}-basis ports"
    else:
        name = "Logical CNOT with open ports"
    g = ZXGraph(name)
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.P, "In_Control"),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(0, 0, 2), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 2), ZXKind.X),
        ZXNode(Position3D(0, 0, 3), ZXKind.P, "Out_Control"),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
        ZXNode(Position3D(0, 1, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 1, 1), ZXKind.Z),
        ZXNode(Position3D(0, 1, 2), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(0, 1, 2), ZXKind.X),
        ZXNode(Position3D(1, 1, 2), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 0), ZXKind.P, "In_Target"),
        ZXNode(Position3D(1, 1, 1), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 1), ZXKind.X),
        ZXNode(Position3D(1, 1, 2), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 2), ZXKind.X),
        ZXNode(Position3D(1, 1, 3), ZXKind.P, "Out_Target"),
    )

    if port_kind != "OPEN":
        g.fill_ports(ZXKind(port_kind))
    return g


def logical_cnot_block_graph(
    support_observable_basis: Literal["Z", "X", "BOTH"],
) -> BlockGraph:
    """Create a block graph for the logical CNOT gate.

    Args:
        support_observable_basis: The observable basis that the block graph can support.
            It can be either "Z", "X", or "BOTH". Note that a cube at the port can only
            support the observable basis opposite to the cube. If "Z", the four ports of
            the block graph are filled with X basis cubes. If "X", the four ports are
            filled with Z basis cubes. If "BOTH", the four ports are left open.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical CNOT gate.
    """
    if support_observable_basis == "BOTH":
        port_kind = "OPEN"
    elif support_observable_basis == "Z":
        port_kind = "X"
    else:
        port_kind = "Z"
    zx_graph = logical_cnot_zx_graph(cast(Literal["Z", "X", "OPEN"], port_kind))
    return zx_graph.to_block_graph("Logical CNOT")
