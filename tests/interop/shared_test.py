from pathlib import Path

import pytest

from tqec.interop.shared import LoadFromAnywhere, int_position_before_scale, offset_y_cube_position
from tqec.utils.position import FloatPosition3D, Position3D


def test_abc_class_does_not_init_by_itself():
    # ABC class cannot be instantiated directly
    with pytest.raises(TypeError) as e:
        _ = LoadFromAnywhere()
    assert "LoadFromAnywhere" in str(e.value)

    filepath = Path(__file__).parent.parent.parent / "assets" / "cnots.bgraph"
    # Abstract method inside ABC class won't trigger because ABC class not instantiated
    with pytest.raises(TypeError) as e:
        parse_method = getattr(LoadFromAnywhere, "parse")
        _ = parse_method(filepath=filepath)
    assert "LoadFromAnywhere" in str(e.value)

    # Concrete method inside ABC class also won't trigger despite being fully defined
    with pytest.raises(TypeError) as e:
        load_method = getattr(LoadFromAnywhere, "load")
        _ = load_method(filepath=filepath)
    assert "LoadFromAnywhere" in str(e.value)


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
    pos_3d, expected_3d = (FloatPosition3D(*pos), FloatPosition3D(*expected))
    assert expected_3d == offset_y_cube_position(pos=pos_3d, pipe_length=2.0)
