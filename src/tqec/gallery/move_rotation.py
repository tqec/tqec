"""Block graph that rotates boundary types by moving logical qubit in spacetime."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def move_rotation(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for moving and rotating the spatial boundaries of a logical qubit.
    Args:
        observable_basis: The observable basis that the block graph can support. If None,
            the ports are left open. Otherwise, the ports are filled with the given basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the move-rotation operation.
    """
    g = BlockGraph("Move Rotation")
    g.add_edge(
        Cube(Position3D(0, 0, 0), Port(), "In"),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(0, 1, 1), ZXCube.from_str("ZZX")),
    )
    g.add_edge(
        Cube(Position3D(0, 1, 1), ZXCube.from_str("ZZX")),
        Cube(Position3D(1, 1, 1), ZXCube.from_str("XZX")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 1), ZXCube.from_str("XZX")),
        Cube(Position3D(1, 1, 2), Port(), "Out"),
    )
    if observable_basis == Basis.Z:
        g.fill_ports({"In": ZXCube.from_str("ZXZ"), "Out": ZXCube.from_str("XZZ")})
    elif observable_basis == Basis.X:
        g.fill_ports({"In": ZXCube.from_str("ZXX"), "Out": ZXCube.from_str("XZX")})

    return g
