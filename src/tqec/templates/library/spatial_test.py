import itertools
from typing import Final, Literal

import pytest

from tqec.compile.specs.enums import JunctionArms
from tqec.exceptions import TQECException
from tqec.plaquette.enums import MeasurementBasis, ResetBasis
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.library.spatial import (
    get_spatial_junction_junction_template,
    get_spatial_junction_qubit_template,
)

_EMPT: Final[RPNGDescription] = RPNGDescription.from_string("---- ---- ---- ----")


def test_4_way_spatial_junction() -> None:
    description = get_spatial_junction_qubit_template(
        "z",
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


def test_3_way_UP_RIGHT_DOWN_spatial_junction() -> None:
    description = get_spatial_junction_qubit_template(
        "z", JunctionArms.UP | JunctionArms.RIGHT | JunctionArms.DOWN
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


def test_3_way_LEFT_UP_RIGHT_spatial_junction() -> None:
    description = get_spatial_junction_qubit_template(
        "z", JunctionArms.LEFT | JunctionArms.UP | JunctionArms.RIGHT
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


def test_2_way_through_spatial_junction() -> None:
    with pytest.raises(TQECException, match=".*I-shaped spatial junctions.*"):
        get_spatial_junction_qubit_template("z", JunctionArms.LEFT | JunctionArms.RIGHT)


def test_2_way_L_shape_spatial_junction() -> None:
    description = get_spatial_junction_qubit_template(
        "z", JunctionArms.DOWN | JunctionArms.RIGHT
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


@pytest.mark.parametrize(
    ["external_stabilizers", "arms", "reset", "measurement"],
    itertools.product(
        ["x", "z"],
        (
            JunctionArms.L_shaped_arms()
            + JunctionArms.T_shaped_arms()
            + JunctionArms.X_shaped_arms()
        ),
        [None, ResetBasis.X, ResetBasis.Z],
        [None, MeasurementBasis.X, MeasurementBasis.Z],
    ),
)
def test_spatial_junction_logical_qubit_always_defines_corners(
    external_stabilizers: Literal["x", "z"],
    arms: JunctionArms,
    reset: ResetBasis | None,
    measurement: MeasurementBasis | None,
) -> None:
    template = get_spatial_junction_qubit_template(
        external_stabilizers, arms, reset, measurement
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
    ["external_stabilizers", "arms", "reset", "measurement"],
    itertools.product(
        ["x", "z"],
        JunctionArms.single_arms(),
        [None, ResetBasis.X, ResetBasis.Z],
        [None, MeasurementBasis.X, MeasurementBasis.Z],
    ),
)
def test_spatial_junction_junctions_never_overwrite_corners(
    external_stabilizers: Literal["x", "z"],
    arms: JunctionArms,
    reset: ResetBasis | None,
    measurement: MeasurementBasis | None,
) -> None:
    template = get_spatial_junction_junction_template(
        external_stabilizers, arms, reset, measurement
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
