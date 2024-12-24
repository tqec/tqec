from typing import Final

from tqec.plaquette.enums import MeasurementBasis, ResetBasis
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.enums import ZObservableOrientation
from tqec.templates.library.hadamard import (
    get_spatial_horizontal_hadamard_template,
    get_spatial_vertical_hadamard_template,
    get_temporal_hadamard_template,
)

_EMPT: Final[RPNGDescription] = RPNGDescription.from_string("---- ---- ---- ----")


def test_hadamard_horizontal_z_observable() -> None:
    hadamard_template = get_temporal_hadamard_template(
        ZObservableOrientation.HORIZONTAL
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1h -x2h -x3h -x4h")
    _ZZZZ = RPNGDescription.from_string("-z1h -z3h -z2h -z4h")
    _XX__ = RPNGDescription.from_string("-x1h -x2h ---- ----")
    ___XX = RPNGDescription.from_string("---- ---- -x3h -x4h")
    _Z_Z_ = RPNGDescription.from_string("-z1h ---- -z2h ----")
    __Z_Z = RPNGDescription.from_string("---- -z3h ---- -z4h")

    assert instantiation == [
        [_EMPT, _EMPT, ___XX, _EMPT, ___XX, _EMPT],
        [__Z_Z, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
        [__Z_Z, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
        [_EMPT, _XX__, _EMPT, _XX__, _EMPT, _EMPT],
    ]


def test_hadamard_vertical_z_observable() -> None:
    hadamard_template = get_temporal_hadamard_template(ZObservableOrientation.VERTICAL)
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1h -x3h -x2h -x4h")
    _ZZZZ = RPNGDescription.from_string("-z1h -z2h -z3h -z4h")
    _ZZ__ = RPNGDescription.from_string("-z1h -z2h ---- ----")
    ___ZZ = RPNGDescription.from_string("---- ---- -z3h -z4h")
    _X_X_ = RPNGDescription.from_string("-x1h ---- -x2h ----")
    __X_X = RPNGDescription.from_string("---- -x3h ---- -x4h")

    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT, ___ZZ, _EMPT],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _EMPT],
    ]


def test_hadamard_vertical_boundary_top_left_is_z_stabilizer() -> None:
    hadamard_template = get_spatial_vertical_hadamard_template(
        top_left_is_z_stabilizer=True
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1- -z3- -z2- -z4-")
    _ZXZX = RPNGDescription.from_string("-z1- -x2- -z3- -x4-")
    _XZXZ = RPNGDescription.from_string("-x1- -z3- -x2- -z4-")
    _ZX__ = RPNGDescription.from_string("-z1- -x2- ---- ----")
    ___XX = RPNGDescription.from_string("---- ---- -x3- -x4-")

    assert instantiation == [
        [_EMPT, ___XX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZX__, _EMPT],
    ]


def test_hadamard_vertical_boundary_top_left_is_x_stabilizer() -> None:
    hadamard_template = get_spatial_vertical_hadamard_template(
        top_left_is_z_stabilizer=False
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _ZXZX = RPNGDescription.from_string("-z1- -x3- -z2- -x4-")
    _XZXZ = RPNGDescription.from_string("-x1- -z2- -x3- -z4-")
    _XZ__ = RPNGDescription.from_string("-x1- -z2- ---- ----")
    ___ZZ = RPNGDescription.from_string("---- ---- -z3- -z4-")

    assert instantiation == [
        [_EMPT, ___ZZ],
        [_XZXZ, _XXXX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZXZX, _ZZZZ],
        [_XZ__, _EMPT],
    ]


def test_hadamard_vertical_boundary_top_left_is_z_stabilizer_reset_z() -> None:
    hadamard_template = get_spatial_vertical_hadamard_template(
        top_left_is_z_stabilizer=True, reset=ResetBasis.Z
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("zx1- -x2- zx3- -x4-")
    _ZZZZ = RPNGDescription.from_string("zz1- -z3- zz2- -z4-")
    _ZXZX = RPNGDescription.from_string("-z1- zx2- -z3- zx4-")
    _XZXZ = RPNGDescription.from_string("-x1- zz3- -x2- zz4-")
    _ZX__ = RPNGDescription.from_string("-z1- zx2- ---- ----")
    ___XX = RPNGDescription.from_string("---- ---- zx3- -x4-")

    assert instantiation == [
        [_EMPT, ___XX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZX__, _EMPT],
    ]


def test_hadamard_vertical_boundary_top_left_is_z_stabilizer_measurement_xz() -> None:
    hadamard_template = get_spatial_vertical_hadamard_template(
        top_left_is_z_stabilizer=True, measurement=MeasurementBasis.X
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1x -x2- -x3x -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1x -z3- -z2x -z4-")
    _ZXZX = RPNGDescription.from_string("-z1- -x2x -z3- -x4x")
    _XZXZ = RPNGDescription.from_string("-x1- -z3x -x2- -z4x")
    _ZX__ = RPNGDescription.from_string("-z1- -x2x ---- ----")
    ___XX = RPNGDescription.from_string("---- ---- -x3x -x4-")

    assert instantiation == [
        [_EMPT, ___XX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZXZX, _ZZZZ],
        [_XZXZ, _XXXX],
        [_ZX__, _EMPT],
    ]


def test_hadamard_horizontal_boundary_horizontal_z_observable() -> None:
    hadamard_template = get_spatial_horizontal_hadamard_template(
        top_left_is_z_stabilizer=True
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1- -z3- -z2- -z4-")
    _ZZXX = RPNGDescription.from_string("-z1- -z2- -x3- -x4-")
    _XXZZ = RPNGDescription.from_string("-x1- -x3- -z2- -z4-")
    __X_Z = RPNGDescription.from_string("---- -x3- ---- -z4-")
    _Z_Z_ = RPNGDescription.from_string("-z1- ---- -z2- ----")

    assert instantiation == [
        [__X_Z, _ZZXX, _XXZZ, _ZZXX, _XXZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
    ]


def test_hadamard_horizontal_boundary_vertical_z_observable() -> None:
    hadamard_template = get_spatial_horizontal_hadamard_template(
        top_left_is_z_stabilizer=False
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    _ZZXX = RPNGDescription.from_string("-z1- -z3- -x2- -x4-")
    _XXZZ = RPNGDescription.from_string("-x1- -x2- -z3- -z4-")
    __Z_X = RPNGDescription.from_string("---- -z3- ---- -x4-")
    _X_X_ = RPNGDescription.from_string("-x1- ---- -x2- ----")

    assert instantiation == [
        [__Z_X, _XXZZ, _ZZXX, _XXZZ, _ZZXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
    ]


def test_hadamard_horizontal_boundary_horizontal_z_observable_reset_z() -> None:
    hadamard_template = get_spatial_horizontal_hadamard_template(
        top_left_is_z_stabilizer=True, reset=ResetBasis.Z
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("zx1- zx2- -x3- -x4-")
    _ZZZZ = RPNGDescription.from_string("zz1- zz3- -z2- -z4-")
    _ZZXX = RPNGDescription.from_string("-z1- -z2- zx3- zx4-")
    _XXZZ = RPNGDescription.from_string("-x1- -x3- zz2- zz4-")
    __X_Z = RPNGDescription.from_string("---- -x3- ---- zz4-")
    _Z_Z_ = RPNGDescription.from_string("zz1- ---- -z2- ----")

    assert instantiation == [
        [__X_Z, _ZZXX, _XXZZ, _ZZXX, _XXZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
    ]


def test_hadamard_horizontal_boundary_horizontal_z_observable_measurement_x() -> None:
    hadamard_template = get_spatial_horizontal_hadamard_template(
        top_left_is_z_stabilizer=True, measurement=MeasurementBasis.X
    )
    instantiation = hadamard_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1x -x2x -x3- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1x -z3x -z2- -z4-")
    _ZZXX = RPNGDescription.from_string("-z1- -z2- -x3x -x4x")
    _XXZZ = RPNGDescription.from_string("-x1- -x3- -z2x -z4x")
    __X_Z = RPNGDescription.from_string("---- -x3- ---- -z4x")
    _Z_Z_ = RPNGDescription.from_string("-z1x ---- -z2- ----")

    assert instantiation == [
        [__X_Z, _ZZXX, _XXZZ, _ZZXX, _XXZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
    ]
