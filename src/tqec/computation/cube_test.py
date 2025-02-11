import pytest

from tqec.computation.cube import Cube, Port, ZXCube
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D


def test_zx_cube_kind() -> None:
    with pytest.raises(TQECException):
        ZXCube(Basis.Z, Basis.Z, Basis.Z)

    kind = ZXCube.from_str("ZXZ")
    assert str(kind) == "ZXZ"
    assert not kind.is_spatial
    assert kind.get_basis_along(Direction3D.X) == Basis.Z
    assert kind.get_basis_along(Direction3D.Y) == Basis.X
    assert kind.get_basis_along(Direction3D.Z) == Basis.Z

    assert len(ZXCube.all_kinds()) == 6


def test_zx_cube() -> None:
    cube = Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
    assert cube.is_zx_cube
    assert not cube.is_spatial
    assert not cube.is_port
    assert not cube.is_y_cube
    assert str(cube) == "ZXZ(0,0,0)"


def test_port() -> None:
    cube = Cube(Position3D(0, 0, 0), Port(), "p")
    assert cube.is_port
    assert str(cube) == "PORT(0,0,0)"

    with pytest.raises(
        TQECException, match="A port cube must have a non-empty port label."
    ):
        Cube(Position3D(0, 0, 0), Port())

    assert cube == Cube(Position3D(0, 0, 0), Port(), "p")
