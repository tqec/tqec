"""Flagged stretched stabilizers for the diagonal spatial Hadamard.

The circuit follows Fig. 4 of https://arxiv.org/abs/2602.09099. The shared
qubit is coupled twice with opposite CNOT directions; ordinary RPNG descriptions
cannot represent this circuit. Geometry projection is shared with the legacy
extended stabilizers, while their circuit construction remains independent.

The orientation-specific gate schedules match the reference implementation:
https://github.com/kishonyWIS/diagonal_syndrome_extraction_surface_code/blob/
5acfd01c0d7814397a135c9253eacb6b6dea6586/spatial_hadamard_manual_construction.py
"""

from dataclasses import replace
from enum import Enum
from typing import Protocol

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.specs.library.generators.extended_stabilizers import (
    ExtendedPlaquetteCollection,
    ExtendedPlaquetteDataQubitsOperations,
)
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits
from tqec.plaquette.rpng import PauliBasis
from tqec.utils.enums import Basis, Orientation
from tqec.utils.instructions import MEASUREMENT_INSTRUCTION_NAMES, RESET_INSTRUCTION_NAMES


class SpatialHadamardFlagMode(str, Enum):
    """Which flag outcomes to measure at the stretched stabilizer interface."""

    NONE = "none"
    PARTIAL = "partial"
    ALL = "all"


class SpatialHadamardFactory(Protocol):
    """Construct an interface circuit with independent outer data operations."""

    def __call__(
        self,
        reset: Basis | None,
        measurement: Basis | None,
        orientation: Orientation,
        *,
        data_operations: ExtendedPlaquetteDataQubitsOperations | None = None,
    ) -> dict[Basis, ExtendedPlaquetteCollection]:
        """Build the two checkerboard parities of the stretched stabilizer."""
        ...


# Outer data gates in the author's reference circuit, indexed by which half
# measures each Pauli basis. HORIZONTAL transposes the qubit coordinates, but
# the surrounding diagonal schedule stays fixed, so its gate times differ.
_DATA_GATE_SCHEDULES = {
    Orientation.VERTICAL: {
        (True, Basis.Z): (3, 2),
        (True, Basis.X): (5, 6),
        (False, Basis.Z): (5, 4),
        (False, Basis.X): (3, 4),
    },
    Orientation.HORIZONTAL: {
        (True, Basis.Z): (4, 5),
        (True, Basis.X): (4, 3),
        (False, Basis.Z): (3, 2),
        (False, Basis.X): (5, 6),
    },
}


def make_diagonal_spatial_hadamard_plaquette_pair(
    top_basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    flag_mode: SpatialHadamardFlagMode = SpatialHadamardFlagMode.PARTIAL,
    orientation: Orientation = Orientation.VERTICAL,
    *,
    data_operations: ExtendedPlaquetteDataQubitsOperations = (
        ExtendedPlaquetteDataQubitsOperations()
    ),
) -> tuple[Plaquette, Plaquette]:
    """Build UP/DOWN halves of a mixed-basis stretched stabilizer.

    The UP half measures ``top_basis`` and the DOWN half its opposite. Z halves
    carry the auxiliary flag; X halves carry the stabilizer outcome. Partial
    flags retain the shared qubit between rounds, resetting it only on entry and
    measuring it only on exit. Reset/measurement mark entry and exit of the
    interface. Outer data operations are specified separately; normally they
    are already supplied by the neighbouring cubes.
    """
    halves = []
    for is_top in (True, False):
        basis = top_basis if is_top else top_basis.flipped()
        is_flag = basis == Basis.Z
        data_y = -1 if is_top else 1
        qubits = PlaquetteQubits(
            [GridQubit(-1, data_y), GridQubit(1, data_y)],
            [GridQubit(0, 0), GridQubit(1, -data_y)],
        )
        left, right = tuple(qubits.data_qubits_indices)
        auxiliary, shared = tuple(qubits.syndrome_qubits_indices)
        moments = [Moment(stim.Circuit()) for _ in range(9)]
        moments[0].append("RX" if is_flag else "RZ", [auxiliary], [])
        if flag_mode != SpatialHadamardFlagMode.PARTIAL or reset is not None:
            moments[0].append("RZ", [shared], [])
        data_reset = data_operations.up_reset if is_top else data_operations.down_reset
        if data_reset is not None:
            moments[0].append(f"R{data_reset.value}", [left, right], [])

        incoming, outgoing = (1, 6) if is_flag else (2, 7)
        moments[incoming].append("CX", [auxiliary, shared] if is_flag else [shared, auxiliary], [])
        moments[outgoing].append("CX", [shared, auxiliary] if is_flag else [auxiliary, shared], [])
        schedules = _DATA_GATE_SCHEDULES[orientation][is_top, basis]
        for data, schedule in zip((left, right), schedules):
            moments[schedule].append(f"C{basis.value}", [auxiliary, data], [])
        if not is_flag or flag_mode != SpatialHadamardFlagMode.NONE:
            moments[8].append("MZ" if is_flag else "MX", [auxiliary], [])
        if flag_mode == SpatialHadamardFlagMode.ALL or (
            flag_mode == SpatialHadamardFlagMode.PARTIAL and measurement is not None
        ):
            moments[8].append("MZ", [shared], [])
        data_measurement = (
            data_operations.up_measurement if is_top else data_operations.down_measurement
        )
        if data_measurement is not None:
            moments[8].append(f"M{data_measurement.value}", [left, right], [])
        name = (
            f"DiagonalSpatialHadamard_{top_basis.value}_{is_top}_{flag_mode.value}"
            f"_{orientation.value}_R{reset}_M{measurement}_D{data_operations}"
        )
        half = Plaquette(
            name,
            qubits,
            ScheduledCircuit(moments, 0, qubits.qubit_map),
            MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
            has_flagged_stabilizer=True,
        )
        if orientation == Orientation.HORIZONTAL:

            def swap_coordinates(qubit: GridQubit) -> GridQubit:
                return GridQubit(qubit.y, qubit.x)

            half = replace(
                half,
                qubits=PlaquetteQubits(
                    [swap_coordinates(q) for q in qubits.data_qubits],
                    [swap_coordinates(q) for q in qubits.syndrome_qubits],
                ),
                circuit=half.circuit.map_to_qubits(swap_coordinates),
            )
        halves.append(half)
    return halves[0], halves[1]


def make_diagonal_spatial_hadamard_extended_plaquettes(
    reset: Basis | None = None,
    measurement: Basis | None = None,
    orientation: Orientation = Orientation.VERTICAL,
    *,
    flag_mode: SpatialHadamardFlagMode = SpatialHadamardFlagMode.PARTIAL,
    data_operations: ExtendedPlaquetteDataQubitsOperations | None = None,
) -> dict[Basis, ExtendedPlaquetteCollection]:
    """Build boundary projections for both checkerboard parities."""
    operations = (
        data_operations
        if data_operations is not None
        else ExtendedPlaquetteDataQubitsOperations(
            reset,
            measurement,
            reset.flipped() if reset else None,
            measurement.flipped() if measurement else None,
        )
    )
    return {
        basis: ExtendedPlaquetteCollection.from_plaquette_pair(
            *make_diagonal_spatial_hadamard_plaquette_pair(
                basis, reset, measurement, flag_mode, orientation, data_operations=operations
            ),
            (PauliBasis[basis.value], PauliBasis[basis.flipped().value]),
            (
                *_DATA_GATE_SCHEDULES[orientation][True, basis],
                *_DATA_GATE_SCHEDULES[orientation][False, basis.flipped()],
            ),
            operations,
            orientation,
        )
        for basis in Basis
    }
