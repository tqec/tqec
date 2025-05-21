import pytest

from tqec.compile.observables.fixed_parity_builder import (
    _get_bottom_stabilizer_cube_qubits,
    _get_bottom_stabilizer_spatial_cube_qubits,
    _get_top_readout_cube_qubits,
    _get_top_readout_pipe_qubits,
    _get_top_readout_spatial_cube_qubits,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.utils.enums import Orientation
from tqec.utils.position import (
    Direction3D,
    PlaquetteShape2D,
    SignedDirection3D,
)


@pytest.mark.parametrize(
    "orientation, expected",
    [
        (Orientation.HORIZONTAL, [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3)]),
        (Orientation.VERTICAL, [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5)]),
    ],
)
def test_get_top_readout_cube_qubits(orientation: Orientation, expected: list[tuple[int, int]]) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = _get_top_readout_cube_qubits(shape, orientation)
    assert coords == expected


@pytest.mark.parametrize(
    "direction, expected",
    [
        (Direction3D.X, [(6, 3)]),
        (Direction3D.Y, [(3, 6)]),
    ],
)
def test_get_top_readout_pipe_qubits(
    direction: Direction3D,
    expected: list[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = _get_top_readout_pipe_qubits(shape, direction)
    assert coords == expected


@pytest.mark.parametrize(
    "connect_to, expected",
    [
        (
            SignedDirection3D(Direction3D.X, True),
            {
                (3.5, 1.5),
                (3.5, 3.5),
                (3.5, 5.5),
                (4.5, 0.5),
                (4.5, 2.5),
                (4.5, 4.5),
                (5.5, 1.5),
                (5.5, 3.5),
                (5.5, 5.5),
            },
        ),
        (
            SignedDirection3D(Direction3D.X, False),
            {
                (0.5, 0.5),
                (0.5, 2.5),
                (0.5, 4.5),
                (1.5, 1.5),
                (1.5, 3.5),
                (1.5, 5.5),
                (2.5, 0.5),
                (2.5, 2.5),
                (2.5, 4.5),
            },
        ),
        (
            SignedDirection3D(Direction3D.Y, True),
            {
                (0.5, 3.5),
                (2.5, 3.5),
                (4.5, 3.5),
                (1.5, 4.5),
                (3.5, 4.5),
                (5.5, 4.5),
                (0.5, 5.5),
                (2.5, 5.5),
                (4.5, 5.5),
            },
        ),
        (
            SignedDirection3D(Direction3D.Y, False),
            {
                (3.5, 0.5),
                (5.5, 0.5),
                (1.5, 0.5),
                (0.5, 1.5),
                (2.5, 1.5),
                (4.5, 1.5),
                (1.5, 2.5),
                (3.5, 2.5),
                (5.5, 2.5),
            },
        ),
    ],
)
def test_get_bottom_stabilizer_cube_qubits(
    connect_to: SignedDirection3D,
    expected: set[tuple[float, float]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = set(_get_bottom_stabilizer_cube_qubits(shape, connect_to))
    assert coords == expected


@pytest.mark.parametrize("k", (1, 2, 10))
def test_get_bottom_stabilizer_spatial_cube_qubits(k: int) -> None:
    w = 2 * k + 2
    shape = PlaquetteShape2D(w, w)
    coords = set(_get_bottom_stabilizer_spatial_cube_qubits(shape))
    assert len(coords) == w**2 // 2
    assert all(c % 0.5 == 0 for cs in coords for c in cs)


@pytest.mark.parametrize(
    "arms, expected",
    [
        (SpatialArms.LEFT | SpatialArms.UP, {(1, 2), (2, 1)}),
        (
            SpatialArms.LEFT | SpatialArms.DOWN,
            {(1, 2), (2, 2), (2, 3)},
        ),
        (
            SpatialArms.UP | SpatialArms.RIGHT,
            {(2, 1), (2, 2), (3, 2)},
        ),
        (SpatialArms.DOWN | SpatialArms.RIGHT, {(2, 3), (3, 2)}),
        (
            SpatialArms.LEFT | SpatialArms.RIGHT,
            {(1, 2), (2, 2), (3, 2)},
        ),
        (
            SpatialArms.UP | SpatialArms.DOWN,
            {(2, 1), (2, 2), (2, 3)},
        ),
    ],
)
def test_get_top_readout_spatial_cube_qubits(
    arms: SpatialArms,
    expected: set[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(4, 4)
    coords = set(_get_top_readout_spatial_cube_qubits(shape, arms))
    assert coords == expected
