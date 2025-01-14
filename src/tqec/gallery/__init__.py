"""Collection of pre-built logical computations.

This module contains functions that build :py:class:`~tqec.computation.zx_graph.ZXGraph` and
:py:class:`~tqec.computation.block_graph.BlockGraph` instances representing the logical computations,
including:

- :mod:`.solo_node`: logical memory
- :mod:`.logical_cnot`: logical CNOT gate
- :mod:`.three_cnots`: three logical CNOT gates compressed in spacetime
"""

from .logical_cnot import logical_cnot_block_graph as logical_cnot_block_graph
from .logical_cnot import logical_cnot_zx_graph as logical_cnot_zx_graph
from .logical_cz import logical_cz_zx_graph as logical_cz_zx_graph
from .logical_cz import logical_cz_block_graph as logical_cz_block_graph
from .three_cnots import three_cnots_block_graph as three_cnots_block_graph
from .three_cnots import three_cnots_zx_graph as three_cnots_zx_graph
