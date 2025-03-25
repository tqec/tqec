"""Synthesis of :py:class:`~tqec.computation.BlockGraph` instance from PyZX
graph."""

from tqec.interop.pyzx.synthesis.positioned import (
    positioned_block_synthesis as positioned_block_synthesis,
)
from tqec.interop.pyzx.synthesis.greedy_bfs import (
    greedy_bfs_block_synthesis as greedy_bfs_block_synthesis,
)

from tqec.interop.pyzx.synthesis.strategy import (
    SynthesisStrategy as SynthesisStrategy,
    block_synthesis as block_synthesis,
)
