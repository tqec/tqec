"""Block graph that represents a Hadamard gate."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def h(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical Hadamard gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If None, the two ports of the block graph will be left open.
            Otherwise, the ports will be filled with the cubes that have the
            initializations and measurements in the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical Hadamard gate.

    """
    g = BlockGraph("Logical Hadamard")
    nodes = [
        (Position3D(0, 0, 0), "P", "In"),
        (Position3D(0, 0, 1), "ZXZ", ""),
        (Position3D(0, 0, 2), "XZX", ""),
        (Position3D(0, 0, 3), "P", "Out"),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3)]
    positions = [node[0] for node in nodes]
    for p0, p1 in pipes:
        g.add_pipe(positions[p0], positions[p1])

    if observable_basis == Basis.Z:
        g.fill_ports({"In": ZXCube.from_str("ZXZ"), "Out": ZXCube.from_str("XZX")})
    elif observable_basis == Basis.X:
        g.fill_ports({"In": ZXCube.from_str("ZXX"), "Out": ZXCube.from_str("XZZ")})
    return g
