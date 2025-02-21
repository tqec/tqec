"""Provides classes and functions to compile a
:class:`~tqec.computation.block_graph.BlockGraph` instance into a
``stim.Circuit``.

This module defines the needed classes and functions to transform a
:class:`~tqec.computation.block_graph.BlockGraph` instance into a fully annotated
``stim.Circuit`` instance that can be simulated using ``stim`` and even executed
on available hardware.
"""

from .block import CompiledBlock as CompiledBlock
from .compile import CompiledGraph as CompiledGraph
from .compile import compile_block_graph as compile_block_graph
from .generation import generate_circuit as generate_circuit
from .specs import BlockBuilder as BlockBuilder
from .specs import CubeSpec as CubeSpec
from .specs import PipeSpec as PipeSpec
from .specs import SubstitutionBuilder as SubstitutionBuilder
