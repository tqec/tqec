import itertools
from typing import Final

import pytest

from tqec.compile.specs.enums import SpatialArms
from tqec.plaquette.rpng import RPNGDescription
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException, TQECWarning

from ._testing import (
    get_spatial_cube_arm_rpng_template,
    get_spatial_cube_qubit_rpng_template,
)

_EMPT: Final[RPNGDescription] = RPNGDescription.empty()
_ZVHE = RPNGDescription.from_string("-z1- -z4- -z3- -z5-")
_ZHHE = RPNGDescription.from_string("-z1- -z2- -z3- -z5-")
_XVHE = RPNGDescription.from_string("-x1- -x4- -x3- -x5-")
_XHHE = RPNGDescription.from_string("-x1- -x2- -x3- -x5-")
_3STL = RPNGDescription.from_string("---- -z4- -z3- -z5-")
_3SBR = RPNGDescription.from_string("-z1- -z4- -z3- ----")


def test_4_way_spatial_junction() -> None:
    description = get_spatial_cube_qubit_rpng_template(
        Basis.Z,
        SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN | SpatialArms.LEFT,
    )
    instantiation = description.instantiate(k=2)

    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _ZVHE, _XHHE, _EMPT],
        [_EMPT, _XVHE, _ZVHE, _XHHE, _ZHHE, _EMPT],
        [_EMPT, _ZHHE, _XHHE, _ZVHE, _XVHE, _EMPT],
        [_EMPT, _XHHE, _ZVHE, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating QubitSpatialCubeTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _EMPT],
        [_EMPT, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


def test_3_way_UP_RIGHT_DOWN_spatial_junction() -> None:
    description = get_spatial_cube_qubit_rpng_template(
        Basis.Z, SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN
    )
    instantiation = description.instantiate(k=2)

    __Z_Z = RPNGDescription.from_string("---- -z3- ---- -z4-")
    assert instantiation == [
        [__Z_Z, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _ZVHE, _XHHE, _EMPT],
        [__Z_Z, _XHHE, _ZVHE, _XHHE, _ZHHE, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _ZVHE, _XVHE, _EMPT],
        [__Z_Z, _XHHE, _ZVHE, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating QubitSpatialCubeTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [__Z_Z, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _EMPT],
        [__Z_Z, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


def test_3_way_LEFT_UP_RIGHT_spatial_junction() -> None:
    description = get_spatial_cube_qubit_rpng_template(
        Basis.Z, SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT
    )
    instantiation = description.instantiate(k=2)

    _ZZ__ = RPNGDescription.from_string("-z1- -z2- ---- ----")

    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _ZVHE, _XHHE, _EMPT],
        [_EMPT, _XVHE, _ZVHE, _XHHE, _ZHHE, _EMPT],
        [_EMPT, _ZHHE, _XVHE, _ZHHE, _XVHE, _EMPT],
        [_EMPT, _XVHE, _ZHHE, _XVHE, _ZHHE, _EMPT],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _ZZ__],
    ]

    expected_warning_message = "^Instantiating QubitSpatialCubeTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_3STL, _EMPT, _EMPT, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _EMPT],
        [_EMPT, _XVHE, _ZHHE, _EMPT],
        [_EMPT, _ZZ__, _EMPT, _ZZ__],
    ]


def test_2_way_through_spatial_junction() -> None:
    with pytest.raises(TQECException, match=".*I-shaped spatial junctions.*"):
        get_spatial_cube_qubit_rpng_template(
            Basis.Z, SpatialArms.LEFT | SpatialArms.RIGHT
        )


def test_2_way_L_shape_spatial_junction() -> None:
    description = get_spatial_cube_qubit_rpng_template(
        Basis.Z, SpatialArms.DOWN | SpatialArms.RIGHT
    )
    instantiation = description.instantiate(k=2)

    __Z_Z = RPNGDescription.from_string("---- -z3- ---- -z4-")
    ___ZZ = RPNGDescription.from_string("---- ---- -z3- -z5-")

    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT, ___ZZ, _EMPT],
        [_EMPT, _3STL, _XVHE, _ZHHE, _XVHE, _EMPT],
        # Note: the third (index 2) plaquette in the line below differs from the
        # reference figure 18. This should have no importance here.
        [__Z_Z, _XHHE, _ZHHE, _XVHE, _ZHHE, _EMPT],
        [_EMPT, _ZVHE, _XHHE, _ZVHE, _XVHE, _EMPT],
        [__Z_Z, _XHHE, _ZVHE, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _EMPT, _EMPT, _3SBR],
    ]

    expected_warning_message = "^Instantiating QubitSpatialCubeTemplate with k=1\\..*"
    with pytest.warns(TQECWarning, match=expected_warning_message):
        instantiation = description.instantiate(k=1)
    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT],
        [_EMPT, _3STL, _XVHE, _EMPT],
        [__Z_Z, _XHHE, _ZVHE, _EMPT],
        [_EMPT, _EMPT, _EMPT, _3SBR],
    ]


@pytest.mark.parametrize(
    ["spatial_boundary_basis", "arms", "reset", "measurement"],
    itertools.product(
        [Basis.X, Basis.Z],
        (
            SpatialArms.L_shaped_arms()
            + SpatialArms.T_shaped_arms()
            + SpatialArms.X_shaped_arms()
        ),
        [None, Basis.X, Basis.Z],
        [None, Basis.X, Basis.Z],
    ),
)
def test_spatial_cube_logical_qubit_always_defines_corners(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None,
    measurement: Basis | None,
) -> None:
    template = get_spatial_cube_qubit_rpng_template(
        spatial_boundary_basis, arms, reset, measurement
    )
    rpng_inst = template.instantiate(k=3)
    # Top left
    if spatial_boundary_basis == Basis.X or (
        SpatialArms.LEFT not in arms and SpatialArms.UP not in arms
    ):
        assert rpng_inst[0][0] == RPNGDescription.empty()
    else:
        assert rpng_inst[0][0] != RPNGDescription.empty()
    # Top right
    if spatial_boundary_basis == Basis.Z or (
        SpatialArms.UP not in arms and SpatialArms.RIGHT not in arms
    ):
        assert rpng_inst[0][-1] == RPNGDescription.empty()
    else:
        assert rpng_inst[0][-1] != RPNGDescription.empty()
    # Bottom right
    if spatial_boundary_basis == Basis.X or (
        SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms
    ):
        assert rpng_inst[-1][-1] == RPNGDescription.empty()
    else:
        assert rpng_inst[-1][-1] != RPNGDescription.empty()
    # Bottom left
    if spatial_boundary_basis == Basis.Z or (
        SpatialArms.DOWN not in arms and SpatialArms.LEFT not in arms
    ):
        assert rpng_inst[-1][0] == RPNGDescription.empty()
    else:
        assert rpng_inst[-1][0] != RPNGDescription.empty()


@pytest.mark.parametrize(
    ["spatial_boundary_basis", "arms", "reset", "measurement"],
    itertools.product(
        [Basis.X, Basis.Z],
        SpatialArms.single_arms(),
        [None, Basis.X, Basis.Z],
        [None, Basis.X, Basis.Z],
    ),
)
def test_spatial_cube_arms_never_overwrite_corners(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None,
    measurement: Basis | None,
) -> None:
    template = get_spatial_cube_arm_rpng_template(
        spatial_boundary_basis, arms, reset, measurement
    )
    match arms:
        case SpatialArms.UP:
            assert 3 not in template.mapping
        case SpatialArms.DOWN:
            assert 2 not in template.mapping
        case SpatialArms.LEFT:
            assert 2 not in template.mapping
        case SpatialArms.RIGHT:
            assert 3 not in template.mapping
