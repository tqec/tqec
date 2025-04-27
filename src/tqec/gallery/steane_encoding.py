"""Block graph that represents a logical stability experiment."""

from pathlib import Path
from tqec.computation.block_graph import BlockGraph
from tqec.utils.enums import Basis

ASSETS_FOLDER = Path(__file__).resolve().parents[3] / "assets"


# TODO:
def steane_encoding(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph that represents a Steane encoding circuit.
    The block graph is created from a DAE file that describes the circuit.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.
    """
    graph = BlockGraph.from_dae_file(ASSETS_FOLDER / "steane_encoding.dae")
    filled_graphs = graph.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
    if observable_basis == Basis.X:
        return filled_graphs[0].graph
    elif observable_basis == Basis.Z:
        return filled_graphs[1].graph
    return graph
