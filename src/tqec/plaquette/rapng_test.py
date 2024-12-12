from tqec.plaquette.rapng import RAPNGDescription

from stim import Circuit as stim_Circuit
import pytest


def test_validate_plaquette_from_rapng_string() -> None:
    # Invalid plaquettes
    rapng_errors = [
        "zz5 -xz1- -xz2- -xz5- -xz4-",  # wrong times for the 2Q gates
        "zz5 -xz1- -xz2- -xz4- -xz4-",  # wrong times for the 2Q gates
        "zz0 -xx1- ----- -xz2- ----",  # wrong meas time
    ]
    # Correct plaquettes
    rapng_examples = [
        "zz6 ----- ----- ----- -----",
        "zz3 -xz1- ----- -xz2- -----",
        "zz5 -xz1- -xz2- -xz3- -xz4-",
    ]
    for rapng in rapng_errors:
        with pytest.raises(ValueError):
            RAPNGDescription.from_extended_string(
                ancilla_and_corners_rapng_string=rapng
            )
    for rapng in rapng_examples:
        RAPNGDescription.from_extended_string(ancilla_and_corners_rapng_string=rapng)


def test_get_plaquette_from_rapng_string() -> None:
    # Usual plaquette corresponding to the ZZZZ stabilizer.
    ancilla_and_corners = "zz5 -xz1- -xz2- -zz3- -zx4-"
    desc = RAPNGDescription.from_extended_string(
        ancilla_and_corners_rapng_string=ancilla_and_corners
    )
    plaquette = desc.get_plaquette()
    expected_circuit_str = """
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RZ 4
TICK
XCZ 4 0
TICK
XCZ 4 1
TICK
ZCZ 4 2
TICK
ZCX 4 3
TICK
MZ 4
"""
    assert stim_Circuit(expected_circuit_str) == plaquette.circuit.get_circuit()