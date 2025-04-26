"""Block graph that represents a logical stability experiment."""

from pathlib import Path
from tqec.computation.block_graph import BlockGraph

ASSETS_FOLDER = Path(__file__).resolve().parents[3] / "assets"


# TODO:
def steane_encoding() -> BlockGraph:
    """Create a block graph that represents a Steane encoding circuit.
    The block graph is created from a DAE file that describes the circuit.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance.
    """
    graph = BlockGraph.from_dae_file(ASSETS_FOLDER / "steane_encoding.dae")

    filled_graphs = graph.fill_ports_for_minimal_simulation()
    return filled_graphs[0].graph
