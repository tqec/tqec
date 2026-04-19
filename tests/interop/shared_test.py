from pathlib import Path

import pytest

from tqec.interop.shared import LoadFromAnywhere, int_position_before_scale, offset_y_cube_position
from tqec.utils.position import FloatPosition3D, Position3D


def test_abc_class_does_not_init_by_itself():
    # ABC class cannot be instantiated directly
    with pytest.raises(TypeError, match=r".* implementation for abstract method .*"):
        _ = LoadFromAnywhere()

    filepath = Path(__file__).parent.parent.parent / "assets" / "cnots.bgraph"
    # Abstract method inside ABC class won't trigger because ABC class not instantiated
    with pytest.raises(TypeError, match=r".* missing 1 required positional argument: .*"):
        _ = LoadFromAnywhere.parse(filepath=filepath)

    # Concrete method inside ABC class also won't trigger despite being fully defined
    with pytest.raises(TypeError, match=r".* missing 1 required positional argument: .*"):
        _ = LoadFromAnywhere.load(filepath=filepath)


@pytest.mark.parametrize(
    "pos, expected",
    [
        [(0.5, 0.0, 0.0), (0, 0, 0)],
        [(1.0, 0.0, 0.0), (0, 0, 0)],
        [(2.0, 0.0, 0.0), (1, 0, 0)],
        [(2.5, 0.0, 0.0), (1, 0, 0)],
    ],
)
def test_int_position_before_scale(pos: tuple[float, float, float], expected: tuple[int, int, int]):
    # NB! Varying pipe lengths already tested via COLLADA tests
    pos, expected = (FloatPosition3D(*pos), Position3D(*expected))
    assert expected == int_position_before_scale(pos=pos, pipe_length=2.0)


@pytest.mark.parametrize(
    "pos, expected",
    [
        [(0.5, 0.0, 0.0), (0.5, 0.0, 0.0)],
        [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        [(2.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        [(2.5, 0.0, 0.0), (2.5, 0.0, 0.0)],
    ],
)
def test_offset_y_cube_position(pos: tuple[float, float, float], expected: tuple[int, int, int]):
    # NB! Varying pipe lengths already tested via COLLADA tests
    pos, expected = (FloatPosition3D(*pos), FloatPosition3D(*expected))
    assert expected == offset_y_cube_position(pos=pos, pipe_length=2.0)
