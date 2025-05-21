"""Synthesis of :py:class:`~tqec.computation.BlockGraph` instance from PyZX
graph.
"""

from tqec.interop.pyzx.synthesis.positioned import (
    positioned_block_synthesis,
)

from tqec.interop.pyzx.synthesis.strategy import (
    SynthesisStrategy,
    block_synthesis,
)
