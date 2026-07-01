import pytest

from tqec.interop.shared import int_position_before_scale, offset_y_half_cube_position
from tqec.utils.position import FloatPosition3D, Position3D


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
    pos_3d, expected_3d = (FloatPosition3D(*pos), Position3D(*expected))
    assert expected_3d == int_position_before_scale(pos=pos_3d, pipe_length=2.0)


@pytest.mark.parametrize(
    "pos, pipe_direction, expected",
    [
        # init (+1): z shifts up by 0.5; x and y are untouched
        [(0.0, 0.0, 0.0), 1, (0.0, 0.0, 0.5)],
        [(3.0, 9.0, 6.0), 1, (3.0, 9.0, 6.5)],
        [(1.25, -7.0, 4.0), 1, (1.25, -7.0, 4.5)],
        # meas (-1): z shifts down by 0.5
        [(0.0, 0.0, 1.0), -1, (0.0, 0.0, 0.5)],
        [(3.0, 9.0, 6.0), -1, (3.0, 9.0, 5.5)],
    ],
)
def test_offset_y_half_cube_position(
    pos: tuple[float, float, float],
    pipe_direction: int,
    expected: tuple[float, float, float],
):
    pos_3d, expected_3d = (FloatPosition3D(*pos), FloatPosition3D(*expected))
    assert expected_3d == offset_y_half_cube_position(pos=pos_3d, pipe_direction=pipe_direction)
