"""Block graph that implements a logical S gate via gate teleportation."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import YHalfCube, ZXCube
from tqec.utils.enums import PauliBasis
from tqec.utils.position import Position3D


def s_gate_teleportation(in_observable_basis: PauliBasis | None = None) -> BlockGraph:
    """Create a block graph representing S gate teleportation.

    Args:
        in_observable_basis: The observable basis that goes into the block graph.
            If None, the ports are left open. Otherwise, the ports are filled with
            the given basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the s gate teleportation operation.

    """
    g = BlockGraph("S Gate Teleportation")
    nodes = [
        (Position3D(0, 0, 0), "P", "In"),
        (Position3D(0, 0, 1), "XZX", ""),
        (Position3D(1, 0, 1), "XZX", ""),
        (Position3D(1, 0, 2), "Y", ""),
        (Position3D(0, 0, 2), "P", "Out"),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (1, 4), (2, 3)]
    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    match in_observable_basis:
        case PauliBasis.Z:
            g.fill_ports({"In": ZXCube.from_str("XZZ"), "Out": ZXCube.from_str("XZZ")})
        case PauliBasis.X:
            g.fill_ports({"In": ZXCube.from_str("XZX"), "Out": YHalfCube()})
        case PauliBasis.Y:
            g.fill_ports({"In": YHalfCube(), "Out": ZXCube.from_str("XZX")})
        case _:
            pass
    return g
