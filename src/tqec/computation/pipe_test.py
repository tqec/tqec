import pytest

from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe, PipeKind
from tqec.enums import Basis
from tqec.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D


def test_pipe_kind() -> None:
    with pytest.raises(Exception, match="Exactly one basis must be None for a pipe."):
        PipeKind(Basis.X, Basis.Z, Basis.X)

    with pytest.raises(Exception, match="Exactly one basis must be None for a pipe."):
        PipeKind(None, None, Basis.X)

    with pytest.raises(Exception, match="Pipe must have different basis walls."):
        PipeKind(None, Basis.X, Basis.X)

    kind = PipeKind.from_str("OXZ")
    assert str(kind) == "OXZ"
    assert kind.direction == Direction3D.X
    assert kind.get_basis_along(Direction3D.X) is None
    assert kind.get_basis_along(Direction3D.Y) == Basis.X
    assert kind.get_basis_along(Direction3D.Z, False) == Basis.Z
    assert kind.is_spatial

    kind = PipeKind.from_str("XZOH")
    assert str(kind) == "XZOH"
    assert kind.direction == Direction3D.Z
    assert kind.is_temporal


def test_pipe_kind_from_cube_kind() -> None:
    assert PipeKind._from_cube_kind(
        ZXCube.from_str("XXZ"), Direction3D.X, True
    ) == PipeKind.from_str("OXZ")
    assert PipeKind._from_cube_kind(
        ZXCube.from_str("XXZ"), Direction3D.Y, True
    ) == PipeKind.from_str("XOZ")
    assert PipeKind._from_cube_kind(
        ZXCube.from_str("XXZ"), Direction3D.Y, False
    ) == PipeKind.from_str("XOZ")
    assert PipeKind._from_cube_kind(
        ZXCube.from_str("ZXZ"), Direction3D.Z, True, True
    ) == PipeKind.from_str("ZXOH")
    assert PipeKind._from_cube_kind(
        ZXCube.from_str("ZXZ"), Direction3D.Z, False, True
    ) == PipeKind.from_str("XZOH")


def test_pipe() -> None:
    with pytest.raises(
        Exception, match="The pipe must connect two nearby cubes in direction Y."
    ):
        Pipe(
            Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
            Cube(Position3D(1, 0, 0), ZXCube.from_str("XXZ")),
            PipeKind.from_str("XOZ"),
        )

    pipe = Pipe(
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        PipeKind.from_str("OXZ"),
    )
    assert pipe.direction == Direction3D.X
    assert pipe.u.position < pipe.v.position
    pipe.check_compatible_with_cubes()
    assert list(iter(pipe)) == [pipe.u, pipe.v]


def test_pipe_compatible() -> None:
    pipe = Pipe(
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        PipeKind.from_str("OZX"),
    )

    with pytest.raises(TQECException, match="The pipe is not compatible"):
        pipe.check_compatible_with_cubes()
