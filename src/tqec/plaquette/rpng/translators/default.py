import functools
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
    """Concrete RPNG translator with configurable measurement timing."""

    QUBITS: Final[PlaquetteQubits] = SquarePlaquetteQubits()

    def __init__(
        self,
        measurement_schedule: int = MEASUREMENT_SCHEDULE,
    ) -> None:
        """Initialize the translator.

        Args:
            measurement_schedule: schedule at which measurements are performed.

        """
        self._measurement_schedule = measurement_schedule

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
        """Generate a plaquette from the provided RPNG description."""
        return self._translate_impl(rpng_description)

    @functools.lru_cache(maxsize=1024)
    def _translate_impl(self, rpng_description: RPNGDescription) -> Plaquette:
        qubits: PlaquetteQubits = deepcopy(type(self).QUBITS)

        data_qubit_indices = list(qubits.data_qubits_indices)
        if len(data_qubit_indices) != 4:
            raise TQECError("Expected 4 data-qubits, got", len(data_qubit_indices))
        used_data_qubit_indices: set[int] = set()
        syndrome_qubit_indices = list(qubits.syndrome_qubits_indices)
        if len(syndrome_qubit_indices) != 1:
            raise TQECError("Expected 1 syndrome qubit, got", len(syndrome_qubit_indices))
        syndrome_qubit_index = syndrome_qubit_indices[0]

        reset_timestep_operations: dict[ExtendedBasis, list[int]] = {}
        meas_timestep_operations: dict[ExtendedBasis, list[int]] = {}
        if (r := rpng_description.ancilla.r) is not None:
            reset_timestep_operations[r.to_extended_basis()] = [syndrome_qubit_index]
        if (g := rpng_description.ancilla.g) is not None:
            meas_timestep_operations[g.to_extended_basis()] = [syndrome_qubit_index]

        entangling_operations: dict[int, tuple[PauliBasis, int]] = {}
        for qi, rpng in enumerate(rpng_description.corners):
            dqi = data_qubit_indices[qi]
            if rpng.r is not None:
                reset_timestep_operations.setdefault(rpng.r, []).append(dqi)
                used_data_qubit_indices.add(dqi)
            if rpng.g is not None:
                meas_timestep_operations.setdefault(rpng.g, []).append(dqi)
                used_data_qubit_indices.add(dqi)
            if rpng.p is not None and rpng.n is not None:
                if rpng.n in entangling_operations:
                    raise TQECError(
                        f"Multiple interactions cannot use schedule {rpng.n} on one plaquette."
                    )
                entangling_operations[rpng.n] = (rpng.p, dqi)
                used_data_qubit_indices.add(dqi)

        circuit = stim.Circuit()
        schedule: list[int] = [0]
        self._add_extended_basis_operation(circuit, "R", reset_timestep_operations)
        circuit.append("TICK", [], [])

        for sched in sorted(entangling_operations):
            p, data_qubit = entangling_operations[sched]
            circuit.append(f"C{p.value.upper()}", [syndrome_qubit_index, data_qubit], [])
            schedule.append(sched)
            circuit.append("TICK", [], [])

        self._add_extended_basis_operation(circuit, "M", meas_timestep_operations)
        schedule.append(self._measurement_schedule)

        kept_data_qubits = [qubits.data_qubits[i] for i in used_data_qubit_indices]
        new_plaquette_qubits = PlaquetteQubits(kept_data_qubits, qubits.syndrome_qubits)
        unfiltered_circuit = ScheduledCircuit.from_circuit(circuit, schedule, qubits.qubit_map)
        filtered_circuit = unfiltered_circuit.filter_by_qubits(new_plaquette_qubits.all_qubits)

        return Plaquette(
            name=str(rpng_description),
            qubits=new_plaquette_qubits,
            circuit=filtered_circuit,
            mergeable_instructions=(
                RESET_INSTRUCTION_NAMES | MEASUREMENT_INSTRUCTION_NAMES | {"H"}
            ),
            debug_information=PlaquetteDebugInformation(rpng_description),
        )
