"""Defines core classes and functions to represent and manipulate quantum
circuits.

This package defines the core class :class:`~schedule.circuit.ScheduledCircuit`
that is used to represent a quantum circuit in the `tqec` library. It also
defines a few core functions:

- :func:`~tqec.circuit.detectors.construction.annotate_detectors_automatically`
  that takes a quantum circuit implementing a complete QEC circuit and adds
  ``DETECTOR`` annotations.
- :func:`~.generation.generate_circuit` that takes a
  :class:`~tqec.templates.base.Template` instance and a description of
  plaquettes via a :class:`~tqec.plaquette.plaquette.Plaquettes` instance and
  generates a :class:`~schedule.circuit.ScheduledCircuit` instance that
  corresponds to the circuit described.
- :func:`~schedule.manipulation.merge_scheduled_circuits` that is a function
  that helps merging several :class:`~schedule.circuit.ScheduledCircuit`
  instances containing gates that are potentially scheduled at the same time
  (but not on the same qubits).

Functions from this package are really the backbone of the :mod:`tqec`
library and are re-used in higher-level packages (such as :mod:`tqec.compile`).
"""

from .detectors.construction import annotate_detectors_automatically
from .generation import generate_circuit
from .schedule import ScheduledCircuit, ScheduleException, merge_scheduled_circuits
