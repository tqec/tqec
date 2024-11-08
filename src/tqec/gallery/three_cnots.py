"""Build the computation graphs that represent three logical CNOT gates
compressed in spacetime."""

from typing import Literal, cast
from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode
from tqec.position import Position3D


def three_cnots_zx_graph(port_kind: Literal["X", "Z", "OPEN"]) -> ZXGraph:
    """Create a ZX graph for three logical CNOT gates compressed in spacetime.

    The three CNOT gates are applied in the following order:

    .. code-block:: text

        q0: -@---@-
             |   |
        q1: -X-@-|-
               | |
        q2: ---X-X-

    Args:
        port_kind: The node kind to fill the six ports of the ZX graph
            It can be either "Z", "X", or "OPEN". If "OPEN", the ports are
            left open. Otherwise, the ports are filled with the given node kind.

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance representing the
        three logical CNOT gates compressed in spacetime.
    """
    g = ZXGraph("Three CNOTs")
    g.add_edge(
        ZXNode(Position3D(-1, 0, 0), ZXKind.P, "Out_a"),
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, -1, 0), ZXKind.P, "In_a"),
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, 1, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(0, 1, 0), ZXKind.Z),
        ZXNode(Position3D(1, 1, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, -1), ZXKind.P, "In_b"),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, -1), ZXKind.P, "In_c"),
        ZXNode(Position3D(1, 1, 0), ZXKind.X),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 0), ZXKind.X),
        ZXNode(Position3D(2, 1, 0), ZXKind.P, "Out_c"),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 0, 2), ZXKind.P, "Out_b"),
    )
    g.add_edge(
        ZXNode(Position3D(1, 0, 1), ZXKind.Z),
        ZXNode(Position3D(1, 1, 1), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(1, 1, 0), ZXKind.X),
        ZXNode(Position3D(1, 1, 1), ZXKind.Z),
    )

    if port_kind != "OPEN":
        g.fill_ports(ZXKind(port_kind.upper()))
    return g


def three_cnots_block_graph(
    support_observable_basis: Literal["X", "Z", "BOTH"],
) -> BlockGraph:
    """Create a block graph for three logical CNOT gates compressed in
    spacetime.

    Args:
        support_observable_basis: The observable basis that the block graph can support.
            It can be either "Z", "X", or "BOTH". Note that a cube at the port can only
            support the observable basis opposite to the cube. If "Z", the six ports of
            the block graph are filled with X basis cubes. If "X", the six ports are
            filled with Z basis cubes. If "BOTH", the ports are left open.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing the
        three logical CNOT gates compressed in spacetime.
    """
    if support_observable_basis == "BOTH":
        port_kind = "OPEN"
    elif support_observable_basis == "Z":
        port_kind = "X"
    else:
        port_kind = "Z"
    zx_graph = three_cnots_zx_graph(cast(Literal["Z", "X", "OPEN"], port_kind))
    return zx_graph.to_block_graph("Three CNOTs")
