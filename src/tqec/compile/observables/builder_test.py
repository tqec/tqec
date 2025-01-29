import pytest

from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.builder import (
    _get_bottom_stabilizer_cube_qubits,
    _get_bottom_stabilizer_spatial_cube_qubits,
    _get_top_readout_cube_qubits,
    _get_top_readout_pipe_qubits,
    _get_top_readout_spatial_cube_qubits,
    _transform_coords_into_grid,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.utils.position import (
    BlockPosition2D,
    Direction3D,
    Position3D,
    Shape2D,
    SignedDirection3D,
)
from tqec.templates.indices.layout import LayoutTemplate
from tqec.templates.indices.qubit import QubitTemplate


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("ZXZ", [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3)]),
        ("XZZ", [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5)]),
    ],
)
def test_get_top_readout_cube_qubits(
    kind: str, expected: list[tuple[int, int]]
) -> None:
    shape = Shape2D(6, 6)
    coords = _get_top_readout_cube_qubits(shape, ZXCube.from_str(kind))
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
    shape = Shape2D(6, 6)
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
    shape = Shape2D(6, 6)
    coords = set(_get_bottom_stabilizer_cube_qubits(shape, connect_to))
    assert coords == expected


@pytest.mark.parametrize("k", (1, 2, 10))
def test_get_bottom_stabilizer_spatial_cube_qubits(k: int) -> None:
    w = 2 * k + 2
    shape = Shape2D(w, w)
    coords = set(_get_bottom_stabilizer_spatial_cube_qubits(shape))
    assert len(coords) == w**2 // 2
    assert all(c % 0.5 == 0 for cs in coords for c in cs)


@pytest.mark.parametrize(
    "arms, expected",
    [
        (SpatialArms.LEFT | SpatialArms.UP, {(0, 2), (1, 2), (2, 0), (2, 1)}),
        (
            SpatialArms.LEFT | SpatialArms.DOWN,
            {(0, 2), (1, 2), (2, 2), (2, 3), (2, 4)},
        ),
        (
            SpatialArms.UP | SpatialArms.RIGHT,
            {(2, 1), (2, 0), (4, 2), (2, 2), (3, 2)},
        ),
        (SpatialArms.DOWN | SpatialArms.RIGHT, {(2, 3), (2, 4), (4, 2), (3, 2)}),
        (
            SpatialArms.LEFT | SpatialArms.RIGHT,
            {(0, 2), (1, 2), (2, 2), (3, 2), (4, 2)},
        ),
        (
            SpatialArms.UP | SpatialArms.DOWN,
            {(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)},
        ),
    ],
)
def test_get_top_readout_spatial_cube_qubits(
    arms: SpatialArms,
    expected: set[tuple[int, int]],
) -> None:
    shape = Shape2D(4, 4)
    coords = set(_get_top_readout_spatial_cube_qubits(shape, arms))
    assert coords == expected


def test_transform_coords_into_grid() -> None:
    template = LayoutTemplate(
        {
            BlockPosition2D(0, 0): QubitTemplate(),
            BlockPosition2D(1, 0): QubitTemplate(),
            BlockPosition2D(1, 1): QubitTemplate(),
        }
    )
    qubit = _transform_coords_into_grid(
        template_slices=[template],
        local_coords=(2, 2),
        block_position=Position3D(1, 1, 0),
        k=5,
    )
    assert qubit == GridQubit(27, 27)

    qubit = _transform_coords_into_grid(
        template_slices=[template],
        local_coords=(3, 1),
        block_position=Position3D(0, 1, 0),
        k=12,
    )
    x = -1 + 3 * 2
    y = (12 * 2 + 2) * 2 - 1 + 1 * 2
    assert qubit == GridQubit(x, y)
