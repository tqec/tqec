# Below a function that mimics how one would generate a Steane encoding using Qrisp.
# The function is called by `./docs/integration/qrisp.ipynb`,
# which shows how to import a Qrisp circuit into TQEC.

from qrisp import QuantumBool, cx, h


def steane_qrisp():
    """Create a Steane code encoding using Qrisp.

    Returns:
        qc: the Qrisp encoding for the Steane code.

    """
    # Ancilla & data qubits
    num_ancilla = 3
    num_data = 7

    ancilla_qubits = [QuantumBool() for _ in range(num_ancilla)]
    data_qubits = [QuantumBool() for _ in range(num_data)]

    h(ancilla_qubits[0])
    cx(ancilla_qubits[0], data_qubits[0])
    cx(ancilla_qubits[0], data_qubits[1])
    cx(ancilla_qubits[0], data_qubits[2])
    cx(ancilla_qubits[0], data_qubits[3])
    h(ancilla_qubits[0])

    # Skip adding measurement gates to avoid issues with PyZX's QASM importer
    # measure(ancilla_qubits[0])

    h(ancilla_qubits[1])
    cx(ancilla_qubits[1], data_qubits[0])
    cx(ancilla_qubits[1], data_qubits[1])
    cx(ancilla_qubits[1], data_qubits[4])
    cx(ancilla_qubits[1], data_qubits[5])
    h(ancilla_qubits[1])

    # Skip adding measurement gates to avoid issues with PyZX's QASM importer
    # measure(ancilla_qubits[1])

    h(ancilla_qubits[2])
    cx(ancilla_qubits[2], data_qubits[0])
    cx(ancilla_qubits[2], data_qubits[2])
    cx(ancilla_qubits[2], data_qubits[4])
    cx(ancilla_qubits[2], data_qubits[6])
    h(ancilla_qubits[2])
    # Skip adding measurement gates to avoid issues with PyZX's QASM importer
    # measure(ancilla_qubits[2])

    return ancilla_qubits + data_qubits
