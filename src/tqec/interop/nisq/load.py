"""Defines functions to load circuits from external NISQ frameworks."""

from pathlib import Path

from qiskit import QuantumCircuit, qasm2
from qrisp import QuantumBool, cx, h
from qrisp.jasp import make_jaspr


# PROCESS MANAGEMENT
def load_nisq_circuit_as_qasm(
    path_to_c: Path, source_framework: str, display_source_c: bool = False
) -> str:
    """Load a circuit from an external NISQ framework and return it as a QASM string.

    Args:
        path_to_c: path to a circuit encoded in the native format of its source framework.
        source_framework: name of the source framework.
        display_source_c: whether to print the input circuit or not.

    Returns:
        qasm_c: string containing the QASM version of the incoming circuit.

    """
    load_from_x_framework = globals()[f"load_from_{source_framework.lower()}"]
    qasm_c = load_from_x_framework(path_to_c, display_source_c=True)

    return qasm_c


# FRAMEWORK SPECIFIC LOAD FUNCTIONS
def load_from_qiskit(path_to_c: Path, display_source_c: bool = False) -> str:
    """Load a circuit from a .qpy (Qiskit) file and return it as a QASM string.

    Args:
        path_to_c: path to a .qpy (Qiskit) circuit.
        display_source_c: whether to print the input circuit or not.

    Returns:
        qasm_c: string containing the QASM version of the incoming .qpy (Qiskit) circuit.

    """
    # START REPLACEABLE SECTION
    # THIS SECTION NEEDS TO BE REPLACED BY AN IMPORT OF AN APPLICABLE FILE
    qc = QuantumCircuit(10)

    qc.h(0)
    qc.cx(0, 3)
    qc.cx(0, 4)
    qc.cx(0, 5)
    qc.cx(0, 6)
    qc.h(0)

    qc.h(1)
    qc.cx(1, 3)
    qc.cx(1, 4)
    qc.cx(1, 7)
    qc.cx(1, 8)
    qc.h(1)

    qc.h(2)
    qc.cx(2, 3)
    qc.cx(2, 5)
    qc.cx(2, 7)
    qc.cx(2, 9)
    qc.h(2)
    # END REPLACEABLE SECTION

    # Update user
    if display_source_c:
        print("\n=> Imported the following Qiskit circuit:\n")
        print(qc)

    # Convert to QASM
    qasm_c = qasm2.dumps(qc)

    # Return QASM version of circuit
    return qasm_c


def load_from_qrisp(path_to_c: Path, display_source_c: bool = False) -> str:
    """Load a circuit from an .xyz (Qrisp) file and returns it as a QASM string.

    Args:
        path_to_c: path to a .qpy (Qiskit) circuit.
        display_source_c: whether to print the input circuit or not.

    Returns:
        qasm_c: string containing the QASM version of the incoming .qpy (Qiskit) circuit.

    """
    # START REPLACEABLE SECTION
    # CHECK IF THIS SECTION CAN BE REPLACED BY AN IMPORT OF AN APPLICABLE FILE
    # HOWEVER, BASED ON SOME RESEARCH INTO THE MATTER QRISP DOES NOT HAVE A NATIVE FILE FORMAT.
    # THEY REALLY DO SEEM TO SAVE THEIR DESIGNS AS PYTHON CODE OR EXPORT DIRECTLY TO QASM.
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

    h(ancilla_qubits[1])
    cx(ancilla_qubits[1], data_qubits[0])
    cx(ancilla_qubits[1], data_qubits[1])
    cx(ancilla_qubits[1], data_qubits[4])
    cx(ancilla_qubits[1], data_qubits[5])
    h(ancilla_qubits[1])

    h(ancilla_qubits[2])
    cx(ancilla_qubits[2], data_qubits[0])
    cx(ancilla_qubits[2], data_qubits[2])
    cx(ancilla_qubits[2], data_qubits[4])
    cx(ancilla_qubits[2], data_qubits[6])
    h(ancilla_qubits[2])
    # END REPLACEABLE SECTION

    c = ancilla_qubits + data_qubits

    # Update user
    if display_source_c:
        print("\n=> Imported the following Qrisp circuit:\n")
        print(c)

    jaspr = make_jaspr(c)()
    qasm_c = jaspr.to_qasm()

    return qasm_c
