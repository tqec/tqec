"""Block graph that rotates boundary types by moving logical qubit in spacetime."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import YHalfCube, ZXCube
from tqec.utils.enums import Basis, PauliBasis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def move_rotation(observable_basis: Basis | PauliBasis | None = None) -> BlockGraph:
    """Create a block graph for moving and rotating the spatial boundaries of a logical qubit.

    Args:
        observable_basis: The observable basis that the block graph can support. If None,
            the ports are left open. Otherwise, the ports are filled with the given basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the move-rotation operation.

    """
    g = BlockGraph("Move Rotation")
    nodes = [
        (Position3D(0, 0, 0), "P", "In"),
        (Position3D(0, 0, 1), "ZXX", ""),
        (Position3D(0, 1, 1), "ZZX", ""),
        (Position3D(1, 1, 1), "XZX", ""),
        (Position3D(1, 1, 2), "P", "Out"),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3), (3, 4)]
    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if observable_basis is None:
        return g

    if str(observable_basis) == "Z":
        g.fill_ports({"In": ZXCube.from_str("ZXZ"), "Out": ZXCube.from_str("XZZ")})
    elif str(observable_basis) == "X":
        g.fill_ports({"In": ZXCube.from_str("ZXX"), "Out": ZXCube.from_str("XZX")})
    elif str(observable_basis) == "Y":
        g.fill_ports({"In": YHalfCube(), "Out": YHalfCube()})
    else:
        raise TQECError(f"Unknown observable basis {observable_basis} for move_rotation.")
    return g
