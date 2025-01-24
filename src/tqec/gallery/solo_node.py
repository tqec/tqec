"""Build a single node computation graph that represents a logical memory or stability experiment."""

from typing import Literal

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode
from tqec.position import Position3D


def solo_node_zx_graph(kind: Literal["Z", "X"]) -> ZXGraph:
    """Create a single node ZX graph with the given kind.

    Args:
        kind: The kind of the node, either "Z" or "X".

    Returns:
        A :py:class:`~tqec.computation.zx_graph.ZXGraph` instance with a single node of the given kind.
    """
    g = ZXGraph(f"Solo {kind} Node")
    g.add_node(ZXNode(Position3D(0, 0, 0), ZXKind(kind)))
    return g


def solo_node_block_graph(
    support_observable_basis: Literal["Z", "X"], is_stability_experiment: bool = False
) -> BlockGraph:
    """Create a block graph with a single cube that can support the given
    observable basis.

    A single cube represents a simple logical memory experiment or a stability experiment.
    For a memory experiment, the cube is initialized in a logical basis state corresponding to the given
    ``support_observable_basis``. For a stability experiment, all the data qubits are initialized in the
    basis opposite to the given ``support_observable_basis``. And the spatial boundary of the cube should
    support the given ``support_observable_basis``.

    Args:
        support_observable_basis: The observable basis that the block graph can support. Either "Z" or "X".

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance with a single cube that can support the
        given observable basis.
    """
    # Memory experiment
    if not is_stability_experiment:
        zx_graph = solo_node_zx_graph("X" if support_observable_basis == "Z" else "Z")
        return zx_graph.to_block_graph(f"Logica {support_observable_basis} Memory")
    # Stability experiment
    # We can not directly build a block graph out of a ZX graph with a single node,
    # it will always be constructed as a memory experiment. So we need to manually
    # create a block graph for a stability experiment.
    g = BlockGraph(f"Stability {support_observable_basis} Experiment")
    if support_observable_basis == "Z":
        g.add_node(Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX")))
    else:  # support_observable_basis == "X"
        g.add_node(Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")))
    return g
