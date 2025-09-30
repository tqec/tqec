"""Block graph that represents a logical stability experiment."""

from tqec.computation.block_graph import BlockGraph
from tqec.utils.enums import Basis
from tqec.utils.paths import GALLERY_DAE_DIR

STEANE_CODE_DAE = GALLERY_DAE_DIR / "steane_encoding.dae"


def steane_encoding(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph that represents a Steane encoding circuit.

    The block graph is created from a DAE file that describes the circuit.

    Args:
        observable_basis: The observable basis that the block graph can support. If
            None, the block graph will have open ports. Otherwise, the ports will be
            filled with the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.

    """
    graph = BlockGraph.from_dae_file(STEANE_CODE_DAE)
    filled_graphs = graph.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
    if observable_basis == Basis.X:
        return filled_graphs[0].graph
    elif observable_basis == Basis.Z:
        return filled_graphs[1].graph
    return graph
