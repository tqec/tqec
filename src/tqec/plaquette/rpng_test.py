import pytest
from stim import Circuit

from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng import RPNGDescription


def test_validate_plaquette_from_rpng_string() -> None:
    # Invalid plaquettes
    rpng_errors = [
        "---- ---- ----",  # wrong length of values
        "---- ---- --- ----",  # wrong length of values
        "-z1- -z2- ---- -z4-",  # wrong number of 2Q gates
        "-z1- -z4- -z3- -z4-",  # wrong times for the 2Q gates
        "-z1- -z0- -z3- -z4-",  # wrong times for the 2Q gates
    ]
    # Valid plaquettes
    rpng_examples = [
        "---- ---- ---- ----",
        "-z1- -z2- -z3- -z4-",
        "-z5- -x2- -x3- -z1-",
        "-x5h -z2z -x3x hz1-",
    ]
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_string(corners_rpng_string=rpng)
    for rpng in rpng_examples:
        RPNGDescription.from_string(corners_rpng_string=rpng)
    # With explicit RG string for the ancilla qubit.
    rpng_errors = [
        "zz -z1- -z0- -z5- -z4-",  # wrong times for the 2Q gates
        "zz -z1- -z2- -z4- -z4-",  # wrong times for the 2Q gates
    ]
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_extended_string(ancilla_and_corners_rpng_string=rpng)


def test_get_plaquette_from_rpng_string() -> None:
    # Usual plaquette corresponding to the ZZZZ stabilizer.
    corners_rpng_str = "-z1- -z3- -z2- -z4-"
    desc = RPNGDescription.from_string(corners_rpng_string=corners_rpng_str)
    plaquette = desc.get_plaquette(meas_time=6)
    expected_circuit_str = """
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RX 4
TICK
CZ 4 0
TICK
CZ 4 2
TICK
CZ 4 1
TICK
CZ 4 3
TICK
TICK
MX 4
"""
    assert Circuit(expected_circuit_str) == plaquette.circuit.get_circuit()

    # Usual plaquette corresponding to the ZXXZ stabilizer with partial initialization.
    corners_rpng_str = "-z1- zx2- zx4- -z5-"
    desc = RPNGDescription.from_string(corners_rpng_string=corners_rpng_str)
    plaquette = desc.get_plaquette(meas_time=6)
    expected_circuit_str = """
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RZ 1 2
RX 4
TICK
CZ 4 0
TICK
CX 4 1
TICK
TICK
CX 4 2
TICK
CZ 4 3
TICK
MX 4
"""
    assert Circuit(expected_circuit_str) == plaquette.circuit.get_circuit()

    # Arbitrary plaquette.
    qubits = SquarePlaquetteQubits()
    corners_rpng_str = "-x5h -z2z -x3x hz1-"
    desc = RPNGDescription.from_string(corners_rpng_string=corners_rpng_str)
    plaquette = desc.get_plaquette(meas_time=6, qubits=qubits)
    expected_circuit_str = """
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
H 3
RX 4
TICK
CZ 4 3
TICK
CZ 4 1
TICK
CX 4 2
TICK
TICK
CX 4 0
TICK
H 0
M 1
MX 2 4
"""
    assert Circuit(expected_circuit_str) == plaquette.circuit.get_circuit()
