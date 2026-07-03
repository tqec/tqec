"""Block graph that represents an S gate."""

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def s(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical S gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If ``Basis.Z``, the ports will be filled with the cubes that have the
            initializations and measurements in the Z basis.
            If None, the two ports of the block graph will be left open so the
            block graph can be composed with neighbouring blocks.
            ``Basis.X`` is not supported: S maps X to Y, and a Y observable cannot
            terminate on a single-basis port face.

    Raises:
        TQECError: If ``observable_basis`` is ``Basis.X``.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical S gate.

    """
    g = BlockGraph("Logical S")
    nodes = [
        (Position3D(0, 0, 0), "P", "In"),
        (Position3D(0, 0, 1), "XZX", ""),
        (Position3D(0, 0, 2), "P", "Out"),
        (Position3D(1, 0, 1), "XZX", ""),
        (Position3D(1, 0, 2), "Y", ""),
    ]
    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (1, 3), (3, 4)]
    positions = [node[0] for node in nodes]
    for p0, p1 in pipes:
        g.add_pipe(positions[p0], positions[p1])

    if observable_basis == Basis.Z:
        g.fill_ports(ZXCube.from_str("XZZ"))
    elif observable_basis == Basis.X:
        raise TQECError(
            "The S gate has no deterministic X-basis observable, "
            "because S maps X to Y = X * Z and "
            "a Y observable cannot terminate on a single-basis port face. "
            "If you want the S gate inside a larger computation, "
            "use observable_basis=None and compose it with neighbouring blocks. "
            "If you want to test S in isolation, use observable_basis=Basis.Z."
        )
    return g
