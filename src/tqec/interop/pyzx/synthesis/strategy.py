"""Collection of strategies for synthesizing a block graph from a ZX graph."""

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pyzx.graph.graph_s import GraphS

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.synthesis.greedy_bfs import greedy_bfs_block_synthesis
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis
from tqec.utils.position import Position3D


class SynthesisStrategy(Enum):
    """Strategy for synthesizing a block graph from a ZX graph."""

    POSITIONED = "POSITIONED"
    """Mapping from a
    :py:class:`~tqec.interop.pyzx.positioned_graph.PositionedZX` instance to a
    block graph.

    This strategy requires specifying the 3D positions of each vertex
    explicitly in the ZX graph. Then the conversion converts each vertex
    by looking at its nearest neighbors to infer the cube kind. The
    conversion maps each vertex to a cube in the block graph and each
    edge to a pipe connecting the corresponding cubes.
    """
    GREEDY_BFS = "GREEDY_BFS"
    """A random greedy breadth-first search strategy."""


def block_synthesis(
    zx_graph: GraphS,
    strategy: SynthesisStrategy = SynthesisStrategy.POSITIONED,
    *,
    positions: Mapping[int, Position3D] | None = None,
    **_kwargs: dict[str, Any],
) -> BlockGraph:
    match strategy:
        case SynthesisStrategy.POSITIONED:
            if positions is None:
                raise ValueError(
                    "The POSITIONED strategy requires specifying positions, but None was given."
                )
            g = PositionedZX(zx_graph, positions)
            return positioned_block_synthesis(g)
        case SynthesisStrategy.GREEDY_BFS:
            return greedy_bfs_block_synthesis(zx_graph)
