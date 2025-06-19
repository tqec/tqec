import pytest

from tqec.plaquette.rpng import RPNGDescription


def test_validate_plaquette_from_rpng_string() -> None:
    # Invalid plaquettes
    rpng_errors = [
        "---- ---- ----",  # wrong length of values
        "---- ---- --- ----",  # wrong length of values
        "-z1- -z4- -z3- -z4-",  # wrong times for the 2Q gates
        "-z1- -z0- -z3- -z4-",  # wrong times for the 2Q gates
    ]
    # Valid plaquettes
    rpng_examples = [
        "---- ---- ---- ----",
        "-z1- -z2- -z3- -z4-",
        "-z5- -x2- -x3- -z1-",
        "-x5h -z2z -x3x hz1-",
        "-z1- -z2- ---- -z4-",
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
