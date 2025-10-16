"""Block graph that represents a logical memory experiment."""

from tqec.computation.block_graph import BlockGraph
from tqec.utils.enums import Basis, PauliBasis
from tqec.utils.position import Position3D


def memory(observable_basis: Basis | PauliBasis = Basis.Z) -> BlockGraph:
    """Create a block graph with a single cube that represents a logical memory experiment.

    Args:
        observable_basis: The logical observable basis for the memory experiment.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.

    """
    g = BlockGraph(f"Logical {observable_basis} Memory Experiment")
    if str(observable_basis) == "Y":
        n1 = g.add_cube(Position3D(0, 0, 0), "Y")
        n2 = g.add_cube(Position3D(0, 0, 1), "Y")
        g.add_pipe(n1, n2, "ZXO")
        return g
    node_kind = f"ZX{observable_basis.value}"
    g.add_cube(Position3D(0, 0, 0), node_kind)
    return g
