"""Provides classes and functions to compile a
:class:`~tqec.computation.block_graph.BlockGraph` instance into a
``stim.Circuit``.

This module defines the needed classes and functions to transform a
:class:`~tqec.computation.block_graph.BlockGraph` instance into a fully annotated
``stim.Circuit`` instance that can be simulated using ``stim`` and even executed
on available hardware.
"""

from .block import CompiledBlock
from .compile import compile_block_graph
from .specs import BlockBuilder, CubeSpec, PipeSpec, SubstitutionBuilder
