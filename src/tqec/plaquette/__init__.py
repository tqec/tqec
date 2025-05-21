"""Defines all the necessary data-structures to represent a plaquette.

This package defines one of the core class of the `tqec` library:
:class:`~.plaquette.Plaquette`.
The :class:`~.plaquette.Plaquette` class represents what is commonly called a
"plaquette" in quantum error correction and is basically a
:class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` instance
representing the computation defining the plaquette.

Because we do not have a module to perform simple geometry operations on qubits
(yet), the :mod:`tqec.plaquette.qubit` module is providing classes to represent
the qubits a plaquette is applied to and perform some operations on them (e.g.,
get the qubits on a specific side of the plaquette).
"""

from ..utils.frozendefaultdict import FrozenDefaultDict
from .enums import PlaquetteOrientation
from .enums import PlaquetteSide
from .plaquette import Plaquette
from .plaquette import Plaquettes
from .plaquette import RepeatedPlaquettes
from .qubit import PlaquetteQubits
from .qubit import SquarePlaquetteQubits
from .rpng import RG
from .rpng import RPNG
from .rpng import RPNGDescription
