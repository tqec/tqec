"""Block graph that represent a CNOT gate."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, ZXCube
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

    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), Port(), label="In_Control"),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(0, 0, 2), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 2), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 3), Port(), label="Out_Control"),
    )
    g.add_edge(
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(0, 1, 1), ZXCube.from_str("ZXX")),
    )
    g.add_edge(
        Cube(Position3D(0, 1, 1), ZXCube.from_str("ZXX")),
        Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 1, 2), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 0), Port(), label="In_Target"),
        Cube(Position3D(1, 1, 1), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 1), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 1, 2), ZXCube.from_str("ZXZ")),
    )
    g.add_edge(
        Cube(Position3D(1, 1, 2), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 1, 3), Port(), label="Out_Target"),
    )
    if observable_basis == Basis.Z:
        g.fill_ports(ZXCube.from_str("ZXZ"))
    elif observable_basis == Basis.X:
        g.fill_ports(ZXCube.from_str("ZXX"))
    return g
