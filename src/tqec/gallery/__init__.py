"""Collection of pre-built logical computations.

This module contains functions that build :py:class:`~tqec.computation.zx_graph.ZXGraph` and
:py:class:`~tqec.computation.block_graph.BlockGraph` instances representing the logical computations,
including:

- :py:mod:`~tqec.gallery.solo_node`: logical memory
- :py:mod:`~tqec.gallery.logical_cnot`: logical CNOT gate
- :py:mod:`~tqec.gallery.three_cnots`: three logical CNOT gates compressed in spacetime
"""

from .solo_node import solo_node_zx_graph, solo_node_block_graph
from .logical_cnot import logical_cnot_zx_graph, logical_cnot_block_graph
from .three_cnots import three_cnots_zx_graph, three_cnots_block_graph
