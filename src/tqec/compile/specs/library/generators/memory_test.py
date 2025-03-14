from typing import Final

from tqec.plaquette.rpng import RPNGDescription
from tqec.utils.enums import Basis, Orientation

from ._testing import (
    get_memory_horizontal_boundary_rpng_template,
    get_memory_qubit_rpng_template,
    get_memory_vertical_boundary_rpng_template,
)

_EMPT: Final[RPNGDescription] = RPNGDescription.empty()
_XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x4-")
_ZZZZ = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
_X_X_ = RPNGDescription.from_string("-x1- ---- -x3- ----")
__X_X = RPNGDescription.from_string("---- -x2- ---- -x4-")
_XX__ = RPNGDescription.from_string("-x1- -x3- ---- ----")
___XX = RPNGDescription.from_string("---- ---- -x2- -x4-")
_Z_Z_ = RPNGDescription.from_string("-z1- ---- -z3- ----")
__Z_Z = RPNGDescription.from_string("---- -z2- ---- -z4-")
_ZZ__ = RPNGDescription.from_string("-z1- -z3- ---- ----")
___ZZ = RPNGDescription.from_string("---- ---- -z2- -z4-")


def test_memory_horizontal_z_observable() -> None:
    memory_template = get_memory_qubit_rpng_template(Orientation.HORIZONTAL)
    instantiation = memory_template.instantiate(k=2)

    assert instantiation == [
        [_EMPT, ___XX, _EMPT, ___XX, _EMPT, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
        [__Z_Z, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _EMPT],
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
        [__Z_Z, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _EMPT],
        [_EMPT, _EMPT, _XX__, _EMPT, _XX__, _EMPT],
    ]


def test_memory_vertical_z_observable() -> None:
    memory_template = get_memory_qubit_rpng_template(Orientation.VERTICAL)
    instantiation = memory_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1- -x3- -x2- -x4-")
    _ZZZZ = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")

    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT, ___ZZ, _EMPT],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _EMPT],
    ]


def test_memory_vertical_z_observable_reset_z() -> None:
    memory_template = get_memory_qubit_rpng_template(
        Orientation.VERTICAL, reset=Basis.Z
    )
    instantiation = memory_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("zx1- zx3- zx2- zx4-")
    _ZZZZ = RPNGDescription.from_string("zz1- zz2- zz3- zz4-")
    _ZZ__ = RPNGDescription.from_string("zz1- zz3- ---- ----")
    ___ZZ = RPNGDescription.from_string("---- ---- zz2- zz4-")
    _X_X_ = RPNGDescription.from_string("zx1- ---- zx3- ----")
    __X_X = RPNGDescription.from_string("---- zx2- ---- zx4-")

    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT, ___ZZ, _EMPT],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _EMPT],
    ]


def test_memory_vertical_z_observable_measure_x() -> None:
    memory_template = get_memory_qubit_rpng_template(
        Orientation.VERTICAL, measurement=Basis.X
    )
    instantiation = memory_template.instantiate(k=2)

    _XXXX = RPNGDescription.from_string("-x1x -x3x -x2x -x4x")
    _ZZZZ = RPNGDescription.from_string("-z1x -z2x -z3x -z4x")
    _ZZ__ = RPNGDescription.from_string("-z1x -z3x ---- ----")
    ___ZZ = RPNGDescription.from_string("---- ---- -z2x -z4x")
    _X_X_ = RPNGDescription.from_string("-x1x ---- -x3x ----")
    __X_X = RPNGDescription.from_string("---- -x2x ---- -x4x")

    assert instantiation == [
        [_EMPT, _EMPT, ___ZZ, _EMPT, ___ZZ, _EMPT],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
        [_EMPT, _ZZ__, _EMPT, _ZZ__, _EMPT, _EMPT],
    ]


def test_memory_vertical_boundary_horizontal_z_observable() -> None:
    memory_template = get_memory_vertical_boundary_rpng_template(Orientation.HORIZONTAL)
    instantiation = memory_template.instantiate(k=2)

    assert instantiation == [
        [___XX, _EMPT],
        [_ZZZZ, _XXXX],
        [_XXXX, _ZZZZ],
        [_ZZZZ, _XXXX],
        [_XXXX, _ZZZZ],
        [_EMPT, _XX__],
    ]


def test_memory_vertical_boundary_vertical_z_observable() -> None:
    memory_template = get_memory_vertical_boundary_rpng_template(Orientation.VERTICAL)
    instantiation = memory_template.instantiate(k=2)

    assert instantiation == [
        [_EMPT, ___ZZ],
        [_ZZZZ, _XXXX],
        [_XXXX, _ZZZZ],
        [_ZZZZ, _XXXX],
        [_XXXX, _ZZZZ],
        [_ZZ__, _EMPT],
    ]


def test_memory_vertical_boundary_vertical_z_observable_reset_z() -> None:
    memory_template = get_memory_vertical_boundary_rpng_template(
        Orientation.VERTICAL, reset=Basis.Z
    )
    instantiation = memory_template.instantiate(k=2)

    _ZZZZl = RPNGDescription.from_string("-z1- zz2- -z3- zz4-")
    _ZZZZr = RPNGDescription.from_string("zz1- -z2- zz3- -z4-")
    _XXXXl = RPNGDescription.from_string("-x1- zx3- -x2- zx4-")
    _XXXXr = RPNGDescription.from_string("zx1- -x3- zx2- -x4-")
    _ZZ__l = RPNGDescription.from_string("-z1- zz3- ---- ----")
    ___ZZr = RPNGDescription.from_string("---- ---- zz2- -z4-")

    assert instantiation == [
        [_EMPT, ___ZZr],
        [_ZZZZl, _XXXXr],
        [_XXXXl, _ZZZZr],
        [_ZZZZl, _XXXXr],
        [_XXXXl, _ZZZZr],
        [_ZZ__l, _EMPT],
    ]


def test_memory_vertical_boundary_vertical_z_observable_measure_x() -> None:
    memory_template = get_memory_vertical_boundary_rpng_template(
        Orientation.VERTICAL, measurement=Basis.X
    )
    instantiation = memory_template.instantiate(k=2)

    _ZZZZl = RPNGDescription.from_string("-z1- -z2x -z3- -z4x")
    _ZZZZr = RPNGDescription.from_string("-z1x -z2- -z3x -z4-")
    _XXXXl = RPNGDescription.from_string("-x1- -x3x -x2- -x4x")
    _XXXXr = RPNGDescription.from_string("-x1x -x3- -x2x -x4-")
    _ZZ__l = RPNGDescription.from_string("-z1- -z3x ---- ----")
    ___ZZr = RPNGDescription.from_string("---- ---- -z2x -z4-")

    assert instantiation == [
        [_EMPT, ___ZZr],
        [_ZZZZl, _XXXXr],
        [_XXXXl, _ZZZZr],
        [_ZZZZl, _XXXXr],
        [_XXXXl, _ZZZZr],
        [_ZZ__l, _EMPT],
    ]


def test_memory_horizontal_boundary_horizontal_z_observable() -> None:
    memory_template = get_memory_horizontal_boundary_rpng_template(
        Orientation.HORIZONTAL
    )
    instantiation = memory_template.instantiate(k=2)

    assert instantiation == [
        [_EMPT, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _Z_Z_],
        [__Z_Z, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _EMPT],
    ]


def test_memory_horizontal_boundary_vertical_z_observable() -> None:
    memory_template = get_memory_horizontal_boundary_rpng_template(Orientation.VERTICAL)
    instantiation = memory_template.instantiate(k=2)

    assert instantiation == [
        [__X_X, _ZZZZ, _XXXX, _ZZZZ, _XXXX, _EMPT],
        [_EMPT, _XXXX, _ZZZZ, _XXXX, _ZZZZ, _X_X_],
    ]


def test_memory_horizontal_boundary_vertical_z_observable_reset_z() -> None:
    memory_template = get_memory_horizontal_boundary_rpng_template(
        Orientation.VERTICAL, reset=Basis.Z
    )
    instantiation = memory_template.instantiate(k=2)

    _XXXXt = RPNGDescription.from_string("-x1- -x3- zx2- zx4-")
    _XXXXb = RPNGDescription.from_string("zx1- zx3- -x2- -x4-")
    _ZZZZt = RPNGDescription.from_string("-z1- -z2- zz3- zz4-")
    _ZZZZb = RPNGDescription.from_string("zz1- zz2- -z3- -z4-")
    __X_Xt = RPNGDescription.from_string("---- -x2- ---- zx4-")
    _X_X_b = RPNGDescription.from_string("zx1- ---- -x3- ----")

    assert instantiation == [
        [__X_Xt, _ZZZZt, _XXXXt, _ZZZZt, _XXXXt, _EMPT],
        [_EMPT, _XXXXb, _ZZZZb, _XXXXb, _ZZZZb, _X_X_b],
    ]


def test_memory_horizontal_boundary_vertical_z_observable_measure_x() -> None:
    memory_template = get_memory_horizontal_boundary_rpng_template(
        Orientation.VERTICAL, measurement=Basis.X
    )
    instantiation = memory_template.instantiate(k=2)

    _XXXXt = RPNGDescription.from_string("-x1- -x3- -x2x -x4x")
    _XXXXb = RPNGDescription.from_string("-x1x -x3x -x2- -x4-")
    _ZZZZt = RPNGDescription.from_string("-z1- -z2- -z3x -z4x")
    _ZZZZb = RPNGDescription.from_string("-z1x -z2x -z3- -z4-")
    __X_Xt = RPNGDescription.from_string("---- -x2- ---- -x4x")
    _X_X_b = RPNGDescription.from_string("-x1x ---- -x3- ----")

    assert instantiation == [
        [__X_Xt, _ZZZZt, _XXXXt, _ZZZZt, _XXXXt, _EMPT],
        [_EMPT, _XXXXb, _ZZZZb, _XXXXb, _ZZZZb, _X_X_b],
    ]
