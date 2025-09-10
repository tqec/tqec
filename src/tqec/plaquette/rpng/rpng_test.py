import pytest

from tqec.plaquette.rpng import RPNGDescription


def test_rpng_description() -> None:
    rpngs0 = RPNGDescription.from_string("---- ---- ---- ----")
    assert all(rpng.is_null for rpng in rpngs0.corners)
    assert rpngs0.get_n(0) is None
    assert not rpngs0.has_reset
    assert not rpngs0.has_measurement

    rpngs1 = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    assert not rpngs1.has_reset
    assert not rpngs1.has_measurement
    for i in range(4):
        assert rpngs1.get_n(i) == i + 1

    rpngs2 = RPNGDescription.from_string("-x5h zz2z -x3x hz1-")
    assert rpngs2.has_reset
    assert rpngs2.has_measurement
    assert rpngs2.get_n(0) == 5
    assert rpngs2.get_r_op(0) is None
    assert rpngs2.get_r_op(1) == "RZ"
    assert rpngs2.get_r_op(3) == "H"
    assert rpngs2.get_g_op(0) == "H"
    assert rpngs2.get_g_op(1) == "MZ"
    assert rpngs2.get_g_op(2) == "MX"
    assert rpngs2.get_g_op(3) is None


def test_validate_plaquette_from_rpng_string() -> None:
    # Invalid plaquettes
    rpng_errors = [
        "---- ---- ----",  # wrong length of values
        "---- ---- --- ----",  # wrong length of values
        "-z1- -z4- -z3- -z4-",  # wrong times for the 2Q gates
        "-z1- -z0- -z3- -z4-",  # wrong times for the 2Q gates
    ]
    # Valid plaquettes
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_string(corners_rpng_string=rpng)
    # With explicit RG string for the ancilla qubit.
    rpng_errors = [
        "zz -z1- -z0- -z5- -z4-",  # wrong times for the 2Q gates
        "zz -z1- -z2- -z4- -z4-",  # wrong times for the 2Q gates
    ]
    for rpng in rpng_errors:
        with pytest.raises(ValueError):
            RPNGDescription.from_extended_string(ancilla_and_corners_rpng_string=rpng)
