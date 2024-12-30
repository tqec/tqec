from typing import Final

import stim
from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.exceptions import TQECException
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.plaquette.rpng import BasisEnum, ExtendedBasisEnum, RPNGDescription
from tqec.plaquette.translators.base import RPNGTranslator


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

    MEASUREMENT_SCHEDULE: Final[int] = 6

    @override
    def translate(
        self,
        rpng_description: RPNGDescription,
        qubits: PlaquetteQubits = SquarePlaquetteQubits(),
    ) -> Plaquette:
        data_qubit_indices = list(qubits.data_qubits_indices)
        if len(data_qubit_indices) != 4:
            raise TQECException("Expected 4 data-qubits, got", len(data_qubit_indices))
        syndrome_qubit_indices = list(qubits.syndrome_qubits_indices)
        if len(syndrome_qubit_indices) != 1:
            raise TQECException(
                "Expected 1 syndrome qubit, got", len(syndrome_qubit_indices)
            )
        syndrome_qubit_index = syndrome_qubit_indices[0]

        reset_timestep_operations: dict[ExtendedBasisEnum, list[int]] = {
            ExtendedBasisEnum.X: [syndrome_qubit_index]
        }
        meas_timestep_operations: dict[ExtendedBasisEnum, list[int]] = {
            ExtendedBasisEnum.X: [syndrome_qubit_index]
        }
        entangling_operations: list[tuple[BasisEnum, int] | None] = [
            None for _ in range(DefaultRPNGTranslator.MEASUREMENT_SCHEDULE - 1)
        ]
        for qi, rpng in enumerate(rpng_description.corners):
            dqi = data_qubit_indices[qi]
            if rpng.r is not None:
                reset_timestep_operations.setdefault(rpng.r, []).append(dqi)
            if rpng.g is not None:
                meas_timestep_operations.setdefault(rpng.g, []).append(dqi)
            if rpng.p is not None and rpng.n is not None:
                entangling_operations[rpng.n - 1] = (rpng.p, dqi)

        circuit = stim.Circuit()
        schedule: list[int] = [0]
        # Add reset operations
        for basis in ExtendedBasisEnum:
            if basis not in reset_timestep_operations:
                continue
            targets = sorted(reset_timestep_operations[basis])
            match basis:
                case ExtendedBasisEnum.H:
                    circuit.append("H", targets, [])
                case ExtendedBasisEnum.X | ExtendedBasisEnum.Y | ExtendedBasisEnum.Z:
                    circuit.append(f"R{basis.value.upper()}", targets, [])
        circuit.append("TICK")
        # Add entangling gates
        for sched, entangling_operation in enumerate(entangling_operations):
            if entangling_operation is None:
                continue
            p, data_qubit = entangling_operation
            circuit.append(
                f"C{p.value.upper()}", [syndrome_qubit_index, data_qubit], []
            )
            schedule.append(sched + 1)
            circuit.append("TICK")
        # Add measurement operations
        for basis in ExtendedBasisEnum:
            if basis not in meas_timestep_operations:
                continue
            targets = sorted(meas_timestep_operations[basis])
            match basis:
                case ExtendedBasisEnum.H:
                    circuit.append("H", sorted(targets), [])
                case ExtendedBasisEnum.X | ExtendedBasisEnum.Y | ExtendedBasisEnum.Z:
                    circuit.append(f"M{basis.value.upper()}", targets, [])
        schedule.append(DefaultRPNGTranslator.MEASUREMENT_SCHEDULE)
        # Return the plaquette
        return Plaquette(
            name=rpng_description.to_string(),
            qubits=qubits,
            circuit=ScheduledCircuit.from_circuit(circuit, schedule, qubits.qubit_map),
        )
