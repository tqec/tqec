from copy import deepcopy
from typing import Final, Literal

import stim
from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.debug import PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.plaquette.rpng import ExtendedBasis, PauliBasis, RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import (
    MEASUREMENT_INSTRUCTION_NAMES,
    RESET_INSTRUCTION_NAMES,
)


class DefaultRPNGTranslator(RPNGTranslator):
    """Default implementation of the RPNGTranslator interface.

    The plaquettes returned have the following properties:

    - the syndrome qubit is always reset in the ``X``-basis,
    - the syndrome qubit is always measured in the ``X``-basis,
    - the syndrome qubit is always the control of the 2-qubit gates used,
    - the 2-qubit gate used is always a ``Z``-controlled Pauli gate,
    - resets (and potentially hadamards) are always scheduled at timestep ``0``,
    - 2-qubit gates are always scheduled at timesteps in ``[1, 5]``,
    - measurements (and potentially hadamards) are always scheduled at timestep
      ``DefaultRPNGTranslator.MEASUREMENT_SCHEDULE`` that is currently equal to
      ``6``,
    - resets and measurements are always ordered from their basis (first ``X``,
      then ``Y``, and finally ``Z``),
    - hadamard gates are always after resets and measurements,
    - targets of reset, measurement and hadamard are always ordered.

    """

    QUBITS: Final[PlaquetteQubits] = SquarePlaquetteQubits()

    @staticmethod
    def _add_extended_basis_operation(
        circuit: stim.Circuit,
        op: Literal["R", "M"],
        timestep_operations: dict[ExtendedBasis, list[int]],
    ) -> None:
        for basis in ExtendedBasis:
            if basis not in timestep_operations:
                continue
            targets = sorted(timestep_operations[basis])
            match basis:
                case ExtendedBasis.H:
                    circuit.append("H", targets, [])
                case ExtendedBasis.X | ExtendedBasis.Y | ExtendedBasis.Z:
                    circuit.append(f"{op}{basis.value.upper()}", targets, [])

    @override
    def translate(self, rpng_description: RPNGDescription) -> Plaquette:
        # The current RPNG notation is very much tied to the qubit arrangement
        # in SquarePlaquetteQubits, hence the explicit value here.
        qubits: PlaquetteQubits = deepcopy(DefaultRPNGTranslator.QUBITS)

        data_qubit_indices = list(qubits.data_qubits_indices)
        if len(data_qubit_indices) != 4:
            raise TQECError("Expected 4 data-qubits, got", len(data_qubit_indices))
        used_data_qubit_indices: set[int] = set()
        syndrome_qubit_indices = list(qubits.syndrome_qubits_indices)
        if len(syndrome_qubit_indices) != 1:
            raise TQECError("Expected 1 syndrome qubit, got", len(syndrome_qubit_indices))
        syndrome_qubit_index = syndrome_qubit_indices[0]

        # Handling syndrome qubit reset/measurement
        reset_timestep_operations: dict[ExtendedBasis, list[int]] = {}
        meas_timestep_operations: dict[ExtendedBasis, list[int]] = {}
        if (r := rpng_description.ancilla.r) is not None:
            reset_timestep_operations[r.to_extended_basis()] = [syndrome_qubit_index]
        if (g := rpng_description.ancilla.g) is not None:
            meas_timestep_operations[g.to_extended_basis()] = [syndrome_qubit_index]
        # Handling data-qubits
        entangling_operations: list[tuple[PauliBasis, int] | None] = [
            None for _ in range(MEASUREMENT_SCHEDULE - 1)
        ]
        for qi, rpng in enumerate(rpng_description.corners):
            dqi = data_qubit_indices[qi]
            if rpng.r is not None:
                reset_timestep_operations.setdefault(rpng.r, []).append(dqi)
                used_data_qubit_indices.add(dqi)
            if rpng.g is not None:
                meas_timestep_operations.setdefault(rpng.g, []).append(dqi)
                used_data_qubit_indices.add(dqi)
            if rpng.p is not None and rpng.n is not None:
                entangling_operations[rpng.n - 1] = (rpng.p, dqi)
                used_data_qubit_indices.add(dqi)

        circuit = stim.Circuit()
        schedule: list[int] = [0]
        # Add reset operations
        self._add_extended_basis_operation(circuit, "R", reset_timestep_operations)
        circuit.append("TICK", [], [])

        # Add entangling gates
        for sched, entangling_operation in enumerate(entangling_operations):
            if entangling_operation is None:
                continue
            p, data_qubit = entangling_operation
            circuit.append(f"C{p.value.upper()}", [syndrome_qubit_index, data_qubit], [])
            schedule.append(sched + 1)
            circuit.append("TICK", [], [])

        # Add measurement operations
        self._add_extended_basis_operation(circuit, "M", meas_timestep_operations)
        schedule.append(MEASUREMENT_SCHEDULE)

        # Filter out unused qubits
        kept_data_qubits = [qubits.data_qubits[i] for i in used_data_qubit_indices]
        new_plaquette_qubits = PlaquetteQubits(kept_data_qubits, qubits.syndrome_qubits)
        unfiltered_circuit = ScheduledCircuit.from_circuit(circuit, schedule, qubits.qubit_map)
        filtered_circuit = unfiltered_circuit.filter_by_qubits(new_plaquette_qubits.all_qubits)

        # Return the plaquette
        return Plaquette(
            name=str(rpng_description),
            qubits=new_plaquette_qubits,
            circuit=filtered_circuit,
            mergeable_instructions=(
                RESET_INSTRUCTION_NAMES | MEASUREMENT_INSTRUCTION_NAMES | {"H"}
            ),
            debug_information=PlaquetteDebugInformation(rpng_description),
        )
