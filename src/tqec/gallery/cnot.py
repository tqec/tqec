"""Block graph that represent a CNOT gate."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def cnot(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical CNOT gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If None, the four ports of the block graph will be left open.
            Otherwise, the ports will be filled with the cubes that have the
            initializations and measurements in the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical CNOT gate.

    """
    g = BlockGraph("Logical CNOT")
    nodes = [
        (Position3D(0, 0, 0), "P", "In_Control"),
        (Position3D(0, 0, 1), "ZXX", ""),
        (Position3D(0, 0, 2), "ZXZ", ""),
        (Position3D(0, 0, 3), "P", "Out_Control"),
        (Position3D(0, 1, 1), "ZXX", ""),
        (Position3D(0, 1, 2), "ZXZ", ""),
        (Position3D(1, 1, 0), "P", "In_Target"),
        (Position3D(1, 1, 1), "ZXZ", ""),
        (Position3D(1, 1, 2), "ZXZ", ""),
        (Position3D(1, 1, 3), "P", "Out_Target"),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5), (5, 8), (6, 7), (7, 8), (8, 9)]

    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if observable_basis == Basis.Z:
        g.fill_ports(ZXCube.from_str("ZXZ"))
    elif observable_basis == Basis.X:
        g.fill_ports(ZXCube.from_str("ZXX"))
    return g
