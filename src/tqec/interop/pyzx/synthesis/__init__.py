"""Synthesis of :py:class:`~tqec.computation.block_graph.BlockGraph` instance from PyZX graph."""

from tqec.interop.pyzx.synthesis.positioned import (
    positioned_block_synthesis as positioned_block_synthesis,
)
from tqec.interop.pyzx.synthesis.strategy import (
    SynthesisStrategy as SynthesisStrategy,
)
from tqec.interop.pyzx.synthesis.strategy import (
    block_synthesis as block_synthesis,
)
