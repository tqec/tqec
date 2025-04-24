"""Collection of pre-built logical computations.

This module contains functions that build :py:class:`~tqec.computation.block_graph.BlockGraph`
instances representing the logical computations, including:

- :mod:`.memory`: memory experiment
- :mod:`.stability`: stability experiment
- :mod:`.cnot`: logical CNOT gate
- :mod:`.cz`: logical CZ gate
- :mod:`.move_rotation`: rotate spatial boundaries by moving the logical qubit in spacetime
- :mod:`.three_cnots`: three logical CNOT gates compressed in spacetime
"""

from .memory import memory as memory
from .stability import stability as stability
from .cnot import cnot as cnot
from .cz import cz as cz
from .move_rotation import move_rotation as move_rotation
from .three_cnots import three_cnots as three_cnots
from .steane_encoding import steane_encoding as steane_encoding
