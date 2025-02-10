"""Block graph that represents three logical CNOT gates compressed in
spacetime."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, ZXCube
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def three_cnots(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for three logical CNOT gates compressed in
    spacetime.

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
    g.add_edge(
        Cube(Position3D(-1, 0, 0), Port(), "Out_a"),
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, -1, 0), Port(), "In_a"),
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(0, 1, 0), ZXCube.from_str("XXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, 1, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 0, -1), Port(), "In_b"),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, -1), Port(), "In_c"),
        Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(2, 1, 0), Port(), "Out_c"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 1), ZXCube.from_str("ZXX")),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(1, 0, 2), Port(), "Out_b"),
    )
    g.add_edge(
        Cube(Position3D(1, 0, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(1, 1, 1), ZXCube.from_str("ZXX")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 1, 1), ZXCube.from_str("ZXX")),
    )

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
