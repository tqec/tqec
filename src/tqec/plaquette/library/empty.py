"""Defines empty plaquettes with an empty circuit."""

from tqec.circuit.schedule import ScheduledCircuit
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import (
    PlaquetteQubits,
    SquarePlaquetteQubits,
)


def empty_plaquette(qubits: PlaquetteQubits) -> Plaquette:
    """Return an empty plaquette on the provided ``qubits``."""
    return Plaquette("empty", qubits, ScheduledCircuit.empty())


def empty_square_plaquette() -> Plaquette:
    """Return an empty plaquette on the regular square qubit arrangement."""
    return empty_plaquette(SquarePlaquetteQubits())
