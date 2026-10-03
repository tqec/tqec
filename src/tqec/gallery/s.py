"""Block graph that represents an S gate."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def s(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical S gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If ``Basis.Z``, the ports will be filled with the cubes that have the
            initializations and measurements in the Z basis. The X observable
            becomes non-deterministic.
            If ``Basis.X``, the ports will be filled with the cubes that have the
            initializations and measurements in the X basis. The Z observable
            becomes non-deterministic.
            If None, the two ports of the block graph will be left open so the
            block graph can be composed with neighbouring blocks.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical S gate.

    """
    cube_kind = "ZXZ" if observable_basis == Basis.X else "XZX"
    port_kind = "ZXX" if observable_basis == Basis.X else "XZZ"

    g = BlockGraph("Logical S")
    nodes = [
        (Position3D(0, 0, 0), "P", "In"),
        (Position3D(0, 0, 1), cube_kind, ""),
        (Position3D(0, 0, 2), "P", "Out"),
        (Position3D(1, 0, 1), cube_kind, ""),
        (Position3D(1, 0, 2), "Y", ""),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (1, 3), (3, 4)]
    positions = [node[0] for node in nodes]
    for p0, p1 in pipes:
        g.add_pipe(positions[p0], positions[p1])

    if observable_basis is not None:
        g.fill_ports(ZXCube.from_str(port_kind))
    return g
