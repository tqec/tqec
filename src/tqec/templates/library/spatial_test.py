import itertools
from typing import Final, Literal

import pytest

from tqec.compile.specs.enums import JunctionArms
from tqec.enums import Basis
from tqec.exceptions import TQECException, TQECWarning
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.library.spatial import (
    get_spatial_junction_arm_template,
    get_spatial_junction_qubit_rpng_template,
)

_EMPT: Final[RPNGDescription] = RPNGDescription.from_string("---- ---- ---- ----")


def test_4_way_spatial_junction() -> None:
    description = get_spatial_junction_qubit_rpng_template(
        Basis.Z,
        JunctionArms.UP | JunctionArms.RIGHT | JunctionArms.DOWN | JunctionArms.LEFT,
    )
    instantiation = description.instantiate(k=2)

    _3STL = RPNGDescription.from_string("---- -z3- -z4- -z5-")
    _3SBR = RPNGDescription.from_string("-z1- -z2- -z4- ----")
    _ZVHE = RPNGDescription.from_string("-z1- -z4- -z3- -z5-")
    _ZHHE = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x5-")
    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZVHE, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZHHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZVHE, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating Qubit4WayJunctionTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


def test_3_way_UP_RIGHT_DOWN_spatial_junction() -> None:
    description = get_spatial_junction_qubit_rpng_template(
        Basis.Z, JunctionArms.UP | JunctionArms.RIGHT | JunctionArms.DOWN
    )
    instantiation = description.instantiate(k=2)

    __Z_Z = RPNGDescription.from_string("---- -z3- ---- -z4-")
    _3SBR = RPNGDescription.from_string("-z1- -z2- -z4- ----")
    _ZVHE = RPNGDescription.from_string("-z1- -z4- -z3- -z5-")
    _ZHHE = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x5-")

    assert instantiation == [
        [__Z_Z, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [__Z_Z, _XXXX, _ZVHE, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [__Z_Z, _XXXX, _ZVHE, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating Qubit4WayJunctionTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [__Z_Z, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _EMPT],
        [__Z_Z, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


def test_3_way_LEFT_UP_RIGHT_spatial_junction() -> None:
    description = get_spatial_junction_qubit_rpng_template(
        Basis.Z, JunctionArms.LEFT | JunctionArms.UP | JunctionArms.RIGHT
    )
    instantiation = description.instantiate(k=2)

    _3STL = RPNGDescription.from_string("---- -z3- -z4- -z5-")
    _ZZ__ = RPNGDescription.from_string("-z1- -z2- ---- ----")
    _ZVHE = RPNGDescription.from_string("-z1- -z4- -z3- -z5-")
    _ZHHE = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x5-")

    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZVHE, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZHHE, _XXXX, _ZHHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZHHE, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _ZZ__],
    ]

    expected_warning_message = "^Instantiating Qubit4WayJunctionTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZZ__, _EMPT, _ZZ__],
    ]


def test_2_way_through_spatial_junction() -> None:
    with pytest.raises(TQECException, match=".*I-shaped spatial junctions.*"):
        get_spatial_junction_qubit_rpng_template(
            Basis.Z, JunctionArms.LEFT | JunctionArms.RIGHT
        )


def test_2_way_L_shape_spatial_junction() -> None:
    description = get_spatial_junction_qubit_rpng_template(
        Basis.Z, JunctionArms.DOWN | JunctionArms.RIGHT
    )
    instantiation = description.instantiate(k=2)

    L__ZZ = RPNGDescription.from_string("---- -z3- ---- -z4-")
    T__ZZ = RPNGDescription.from_string("---- ---- -z3- -z4-")
    _3STL = RPNGDescription.from_string("---- -z2- -z4- -z5-")
    _3SBR = RPNGDescription.from_string("-z1- -z2- -z4- ----")
    _ZVHE = RPNGDescription.from_string("-z1- -z4- -z3- -z5-")
    _ZHHE = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x5-")

    assert instantiation == [
        [_EMPT, _EMPT, T__ZZ, _EMPT, T__ZZ, _EMPT],
        [_EMPT, _3STL, _XXXX, _ZHHE, _XXXX, _EMPT],
        [L__ZZ, _XXXX, _ZHHE, _XXXX, _ZHHE, _EMPT],
        [_EMPT, _ZVHE, _XXXX, _ZVHE, _XXXX, _EMPT],
        [L__ZZ, _XXXX, _ZVHE, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating Qubit4WayJunctionTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_EMPT, _EMPT, T__ZZ, _EMPT],
        [_EMPT, _3STL, _XXXX, _EMPT],
        [L__ZZ, _XXXX, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


@pytest.mark.parametrize(
    ["spatial_boundary_basis", "arms", "reset", "measurement"],
    itertools.product(
        [Basis.X, Basis.Z],
        (
            JunctionArms.L_shaped_arms()
            + JunctionArms.T_shaped_arms()
            + JunctionArms.X_shaped_arms()
        ),
        [None, Basis.X, Basis.Z],
        [None, Basis.X, Basis.Z],
    ),
)
def test_spatial_junction_logical_qubit_always_defines_corners(
    spatial_boundary_basis: Basis,
    arms: JunctionArms,
    reset: Basis | None,
    measurement: Basis | None,
) -> None:
    template = get_spatial_junction_qubit_rpng_template(
        spatial_boundary_basis, arms, reset, measurement
    )
    rpng_inst = template.instantiate(k=3)
    if arms == JunctionArms.RIGHT | JunctionArms.DOWN:
        assert rpng_inst[0][0] == RPNGDescription.from_string("---- ---- ---- ----")
    else:
        assert rpng_inst[0][0] != RPNGDescription.from_string("---- ---- ---- ----")

    if arms == JunctionArms.LEFT | JunctionArms.UP:
        assert rpng_inst[-1][-1] == RPNGDescription.from_string("---- ---- ---- ----")
    else:
        assert rpng_inst[-1][-1] != RPNGDescription.from_string("---- ---- ---- ----")

    assert rpng_inst[0][-1] == RPNGDescription.from_string("---- ---- ---- ----")
    assert rpng_inst[-1][0] == RPNGDescription.from_string("---- ---- ---- ----")


@pytest.mark.parametrize(
    ["spatial_boundary_basis", "arms", "reset", "measurement"],
    itertools.product(
        [Basis.X, Basis.Z],
        JunctionArms.single_arms(),
        [None, Basis.X, Basis.Z],
        [None, Basis.X, Basis.Z],
    ),
)
def test_spatial_junction_junctions_never_overwrite_corners(
    spatial_boundary_basis: Basis,
    arms: JunctionArms,
    reset: Basis | None,
    measurement: Basis | None,
) -> None:
    template = get_spatial_junction_arm_template(
        spatial_boundary_basis, arms, reset, measurement
    )
    match arms:
        case JunctionArms.UP:
            assert 3 not in template.mapping
        case JunctionArms.DOWN:
            assert 2 not in template.mapping
        case JunctionArms.LEFT:
            assert 2 not in template.mapping
        case JunctionArms.RIGHT:
            assert 3 not in template.mapping
