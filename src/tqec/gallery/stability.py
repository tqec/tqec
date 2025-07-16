"""Block graph that represents a logical stability experiment."""

from tqec.computation.block_graph import BlockGraph
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def stability(observable_basis: Basis = Basis.Z) -> BlockGraph:
    """Create a block graph with a single cube that represents a logical stability experiment.

    Args:
        observable_basis: The logical observable basis for the memory experiment.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.

    """
    g = BlockGraph(f"{observable_basis} Basis Stability Experiment")
    node_kind = "ZZX" if observable_basis == Basis.Z else "XXZ"
    g.add_cube(Position3D(0, 0, 0), node_kind)
    return g
