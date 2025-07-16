"""Provides code to compile a block graph instance into a ``stim.Circuit``.

This module defines the needed classes and functions to transform a
:class:`~tqec.computation.block_graph.BlockGraph` instance into a fully annotated
``stim.Circuit`` instance that can be simulated using ``stim`` and even executed
on available hardware.

"""

from .compile import compile_block_graph as compile_block_graph
