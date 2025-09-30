"""Defines :class:`.ScheduledCircuit` used to represent quantum circuits in the :mod:`tqec` package.

This module defines one of the main class of the :mod:`tqec` package,
:class:`~.circuit.ScheduledCircuit`, and several functions to modify or create
instances:

- :func:`~.manipulation.merge_scheduled_circuits` that takes several instances of
  :class:`~.circuit.ScheduledCircuit` and merge them into one instance,
- :func:`~.manipulation.relabel_circuits_qubit_indices` that takes several
  instances of :class:`~.circuit.ScheduledCircuit` and relabel their qubits to
  avoid any index clash when merging,
- :func:`~.manipulation.remove_duplicate_instructions` that removes some
  instructions when they are duplicated in a :class:`~tqec.circuit.moment.Moment`
  instance.

"""

from .circuit import ScheduledCircuit as ScheduledCircuit
from .exception import ScheduleError as ScheduleError
from .manipulation import merge_scheduled_circuits as merge_scheduled_circuits
from .manipulation import (
    relabel_circuits_qubit_indices as relabel_circuits_qubit_indices,
)
from .manipulation import remove_duplicate_instructions as remove_duplicate_instructions
from .schedule import Schedule as Schedule
