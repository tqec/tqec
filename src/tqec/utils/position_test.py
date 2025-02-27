import pytest

from tqec.utils.position import (
    Direction3D,
    Position2D,
    Position3D,
    Shape2D,
    SignedDirection3D,
)


def test_position() -> None:
    pos = Position2D(1, 3)
    assert pos.x == 1
    assert pos.y == 3


def test_shape() -> None:
    shape = Shape2D(2, 5)
    assert shape.x == 2
    assert shape.y == 5
    assert shape.to_numpy_shape() == (5, 2)


def test_position_3d() -> None:
    p1 = Position3D(0, 0, 0)
    assert p1.as_tuple() == (0, 0, 0)
    assert p1.shift_by(1, 2, 3) == Position3D(1, 2, 3)
    assert p1.is_neighbour(Position3D(0, 0, 1))
    assert p1.is_neighbour(Position3D(0, 1, 0))
    assert p1.is_neighbour(Position3D(-1, 0, 0))
    assert not p1.is_neighbour(Position3D(1, 0, 1))
    assert not p1.is_neighbour(Position3D(0, -1, 1))


def test_signed_direction() -> None:
    sd = SignedDirection3D.from_string("+X")
    assert sd.direction == Direction3D.X
    assert sd.towards_positive

    sd = SignedDirection3D.from_string("-Z")
    assert sd.direction == Direction3D.Z
    assert not sd.towards_positive


@pytest.mark.parametrize(
    "source,sink,is_neighbour",
    [
        ((0, 0), (0, 0), False),
        ((0, 0), (0, 1), True),
        ((0, 0), (0, -1), True),
        ((0, 0), (1, 0), True),
        ((0, 0), (-1, 0), True),
        ((0, 0), (1, 1), False),
        ((1, 0), (0, 1), False),
    ],
)
def test_is_neighbour(
    source: tuple[int, int], sink: tuple[int, int], is_neighbour: bool
) -> None:
    assert Position2D(*source).is_neighbour(Position2D(*sink)) == is_neighbour


@pytest.mark.parametrize(
    "source,sink,expected_direction",
    [
        (Position3D(0, 0, 0), Position3D(1, 0, 0), Direction3D.X),
        (Position3D(-1, 0, 0), Position3D(0, 0, 0), Direction3D.X),
        (Position3D(0, 0, 0), Position3D(0, 1, 0), Direction3D.Y),
        (Position3D(0, -1, 0), Position3D(0, 0, 0), Direction3D.Y),
        (Position3D(0, 0, 0), Position3D(0, 0, 1), Direction3D.Z),
        (Position3D(0, 0, -1), Position3D(0, 0, 0), Direction3D.Z),
    ],
)
def test_from_neighbouring_positions(
    source: Position3D, sink: Position3D, expected_direction: Direction3D
) -> None:
    assert Direction3D.from_neighbouring_positions(source, sink) == expected_direction


def test_from_neighbouring_positions_invalid() -> None:
    with pytest.raises(AssertionError):
        Direction3D.from_neighbouring_positions(
            Position3D(0, 0, 0), Position3D(-1, 0, 0)
        )
    with pytest.raises(AssertionError):
        Direction3D.from_neighbouring_positions(
            Position3D(0, 0, 0), Position3D(1, 0, 1)
        )
