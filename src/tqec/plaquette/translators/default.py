import stim
from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.exceptions import TQECException
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.translators.base import RPNGTranslator


class DefaultRPNGTranslator(RPNGTranslator):
    """Default implementation of the RPNGTranslator interface.

    The plaquettes returned have the following properties:

    - the syndrome qubit is always reset in the X-basis,
    - the syndrome qubit is always measured in the X-basis,
    - the syndrome qubit is always the control of the 2-qubit gates used,
    - the 2-qubit gate used is always a Z-controlled Pauli gate.

    """

    @override
    def translate(
        self,
        rpng_description: RPNGDescription,
        measurement_schedule: int,
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

        num_timesteps = measurement_schedule + 1
        subcircuits = [stim.Circuit() for _ in range(num_timesteps)]
        subcircuits[0].append("RX", [syndrome_qubit_index], [])
        subcircuits[-1].append("MX", [syndrome_qubit_index], [])
        for qi, rpng in enumerate(rpng_description.corners):
            # 2Q gates.
            qubit = data_qubit_indices[qi]
            if rpng.n and rpng.p:
                if rpng.n >= measurement_schedule:
                    raise ValueError(
                        "The measurement time must be larger than the 2Q gate time."
                    )
                subcircuits[rpng.n].append(
                    f"C{rpng.p.value.upper()}", [syndrome_qubit_index, qubit], []
                )
            # Data reset or Hadamard.
            r_op = rpng.get_r_op()
            if r_op is not None:
                subcircuits[0].append(r_op, [qubit], [])
            # Data measurement or Hadamard.
            g_op = rpng.get_g_op()
            if g_op is not None:
                subcircuits[-1].append(g_op, [qubit], [])

        final_circuit = stim.Circuit()
        for circuit in subcircuits:
            final_circuit += circuit
            final_circuit.append("TICK")

        return Plaquette(
            name=rpng_description.to_string(),
            qubits=qubits,
            circuit=ScheduledCircuit.from_circuit(
                final_circuit, qubit_map=qubits.qubit_map
            ),
        )
