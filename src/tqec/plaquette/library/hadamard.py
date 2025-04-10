"""define the plaquettes for implementing logical Hadamard transition."""

from __future__ import annotations

import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.debug import PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import XYZBasis
from tqec.utils.enums import Basis


SCHEDULES = [0, 1, 2, 3, 4, MEASUREMENT_SCHEDULE]


def shift_x_stabilizer_to_left_plaquette(
    mq_reset: Basis, mq_measurement: Basis, debug_basis: XYZBasis | None = XYZBasis.Z
) -> Plaquette:
    qubits = SquarePlaquetteQubits()

    circuit = stim.Circuit(f"""
R{mq_reset.value} 0
TICK
CX 0 1
TICK
CX 0 3
TICK
CX 2 0
TICK
CX 1 0
TICK
M{mq_measurement.value} 0
""")
    scheduled_circuit = ScheduledCircuit.from_circuit(
        circuit, SCHEDULES, qubits.qubit_map
    )
    return Plaquette(
        f"shift_x_stabilizer_to_left_R{mq_reset}_M{mq_measurement}",
        qubits,
        scheduled_circuit,
        debug_information=PlaquetteDebugInformation(basis=debug_basis),
    )


def shift_z_stabilizer_to_up_plaquette(
    mq_reset: Basis, mq_measurement: Basis, debug_basis: XYZBasis | None = XYZBasis.Z
) -> Plaquette:
    qubits = SquarePlaquetteQubits()

    circuit = stim.Circuit(f"""
R{mq_reset.value} 0
TICK
CX 1 0
TICK
CX 2 0
TICK
CX 0 3
TICK
CX 0 1
TICK
M{mq_measurement.value} 0
""")
    scheduled_circuit = ScheduledCircuit.from_circuit(
        circuit, SCHEDULES, qubits.qubit_map
    )
    return Plaquette(
        f"shift_z_stabilizer_to_up_R{mq_reset}_M{mq_measurement}",
        qubits,
        scheduled_circuit,
        debug_information=PlaquetteDebugInformation(basis=debug_basis),
    )
