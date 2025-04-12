"""define the plaquettes for implementing logical Hadamard transition."""

from __future__ import annotations

import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.debug import PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import XYZBasis
from tqec.utils.enums import Basis, Orientation


def make_fixed_bulk_realignment_plaquette(
    stabilizer_basis: Basis,
    z_orientation: Orientation,
    mq_reset: Basis,
    mq_measurement: Basis,
    debug_basis: XYZBasis | None = None,
) -> Plaquette:
    """Make the plaquette used for fixed-bulk temporal Hadamard transition."""
    qubits = SquarePlaquetteQubits()
    cx_targets: list[tuple[int, int]]
    # used to match the 5-timestep schedule in the other part of computation
    cx_schedule: list[int]
    match stabilizer_basis, z_orientation:
        case Basis.Z, Orientation.VERTICAL:
            cx_targets = [(0, 4), (1, 4), (4, 2), (4, 0)]
            cx_schedule = [1, 2, 3, 5]
        case Basis.Z, Orientation.HORIZONTAL:
            cx_targets = [(0, 4), (2, 4), (4, 1), (4, 0)]
            cx_schedule = [1, 3, 4, 5]
        case Basis.X, Orientation.VERTICAL:
            cx_targets = [(4, 0), (4, 2), (1, 4), (0, 4)]
            cx_schedule = [1, 3, 4, 5]
        case Basis.X, Orientation.HORIZONTAL:
            cx_targets = [(4, 0), (4, 1), (2, 4), (0, 4)]
            cx_schedule = [1, 2, 3, 5]
    circuit = stim.Circuit()
    circuit.append(f"R{mq_reset.value}", qubits.syndrome_qubits_indices, [])
    circuit.append("TICK")
    for targets in cx_targets:
        circuit.append("CX", targets, [])
        circuit.append("TICK")
    circuit.append(f"M{mq_measurement.value}", qubits.syndrome_qubits_indices, [])
    circuit.append("H", qubits.data_qubits_indices, [])
    schedule = [0, *cx_schedule, MEASUREMENT_SCHEDULE]
    scheduled_circuit = ScheduledCircuit.from_circuit(
        circuit, schedule, qubits.qubit_map
    )
    return Plaquette(
        f"fixed_bulk_realignment_{stabilizer_basis}_{z_orientation.value}_R{mq_reset}_M{mq_measurement}",
        qubits,
        scheduled_circuit,
        mergeable_instructions=frozenset({"H"}),
        debug_information=PlaquetteDebugInformation(basis=debug_basis),
    )
