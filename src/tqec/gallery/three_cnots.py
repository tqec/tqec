"""Block graph that represents three logical CNOT gates compressed in spacetime."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def three_cnots(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for three logical CNOT gates compressed in spacetime.

    The three CNOT gates are applied in the following order:

    .. code-block:: text

        q0: -@---@-
             |   |
        q1: -X-@-|-
               | |
        q2: ---X-X-

    Args:
        observable_basis: The observable basis that the block graph can support. If
            None, the block graph will have open ports. Otherwise, the ports will be
            filled with the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing the
        three logical CNOT gates compressed in spacetime.

    """
    g = BlockGraph("Three CNOTs")
    nodes = [
        (Position3D(-1, 0, 0), "P", "Out_a"),
        (Position3D(0, 0, 0), "XXZ", ""),
        (Position3D(0, -1, 0), "P", "In_a"),
        (Position3D(0, 1, 0), "XXZ", ""),
        (Position3D(1, 0, 0), "ZXZ", ""),
        (Position3D(1, 1, 0), "ZXZ", ""),
        (Position3D(1, 0, -1), "P", "In_b"),
        (Position3D(1, 1, -1), "P", "In_c"),
        (Position3D(1, 0, 1), "ZXX", ""),
        (Position3D(1, 1, 1), "ZXX", ""),
        (Position3D(2, 1, 0), "P", "Out_c"),
        (Position3D(1, 0, 2), "P", "Out_b"),
    ]

    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [
        (1, 0),
        (1, 2),
        (1, 3),
        (1, 4),
        (4, 6),
        (4, 8),
        (5, 3),
        (5, 9),
        (5, 10),
        (5, 7),
        (8, 11),
        (8, 9),
    ]
    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if observable_basis == Basis.Z:
        g.fill_ports(
            {
                "In_a": ZXCube.from_str("XZZ"),
                "In_b": ZXCube.from_str("ZXZ"),
                "In_c": ZXCube.from_str("ZXZ"),
                "Out_a": ZXCube.from_str("ZXZ"),
                "Out_b": ZXCube.from_str("ZXZ"),
                "Out_c": ZXCube.from_str("ZXZ"),
            }
        )
    elif observable_basis == Basis.X:
        g.fill_ports(
            {
                "In_a": ZXCube.from_str("XXZ"),
                "In_b": ZXCube.from_str("ZXX"),
                "In_c": ZXCube.from_str("ZXX"),
                "Out_a": ZXCube.from_str("XXZ"),
                "Out_b": ZXCube.from_str("ZXX"),
                "Out_c": ZXCube.from_str("XXZ"),
            }
        )
    return g
