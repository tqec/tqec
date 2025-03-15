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
from tqec.templates.layout import LayoutTemplate
from tqec.templates.qubit import QubitTemplate
from tqec.utils.enums import Basis
from tqec.utils.position import (
    BlockPosition2D,
    Direction3D,
    PlaquetteShape2D,
    Position3D,
    SignedDirection3D,
)


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
    shape = PlaquetteShape2D(6, 6)
    coords = _get_top_readout_cube_qubits(shape, ZXCube.from_str(kind))
    assert coords == expected


@pytest.mark.parametrize(
    "direction, spatial_hadamard, expected",
    [
        (Direction3D.X, False, [(6, 3)]),
        (Direction3D.Y, False, [(3, 6)]),
        (Direction3D.X, True, []),
    ],
)
def test_get_top_readout_pipe_qubits(
    direction: Direction3D,
    spatial_hadamard: bool,
    expected: list[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = _get_top_readout_pipe_qubits(shape, direction, spatial_hadamard)
    assert coords == expected


@pytest.mark.parametrize(
    "connect_to, stabilizer_basis, spatial_hadamard, expected",
    [
        (
            SignedDirection3D(Direction3D.X, True),
            Basis.Z,
            False,
            [
                (3.5, 1.5),
                (3.5, 3.5),
                (3.5, 5.5),
                (4.5, 0.5),
                (4.5, 2.5),
                (4.5, 4.5),
                (5.5, 1.5),
                (5.5, 3.5),
                (5.5, 5.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.X, True),
            Basis.Z,
            True,
            [
                (3.5, 1.5),
                (3.5, 3.5),
                (3.5, 5.5),
                (4.5, 0.5),
                (4.5, 2.5),
                (4.5, 4.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.X, False),
            Basis.Z,
            False,
            [
                (0.5, 0.5),
                (0.5, 2.5),
                (0.5, 4.5),
                (1.5, 1.5),
                (1.5, 3.5),
                (1.5, 5.5),
                (2.5, 0.5),
                (2.5, 2.5),
                (2.5, 4.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.X, False),
            Basis.Z,
            True,
            [
                (0.5, 0.5),
                (0.5, 2.5),
                (0.5, 4.5),
                (1.5, 1.5),
                (1.5, 3.5),
                (1.5, 5.5),
                (2.5, 0.5),
                (2.5, 2.5),
                (2.5, 4.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.Y, True),
            Basis.Z,
            False,
            [
                (0.5, 4.5),
                (1.5, 3.5),
                (1.5, 5.5),
                (2.5, 4.5),
                (3.5, 3.5),
                (3.5, 5.5),
                (4.5, 4.5),
                (5.5, 3.5),
                (5.5, 5.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.Y, True),
            Basis.Z,
            True,
            [
                (0.5, 4.5),
                (1.5, 3.5),
                (2.5, 4.5),
                (3.5, 3.5),
                (4.5, 4.5),
                (5.5, 3.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.Y, False),
            Basis.Z,
            False,
            [
                (0.5, 0.5),
                (0.5, 2.5),
                (1.5, 1.5),
                (2.5, 0.5),
                (2.5, 2.5),
                (3.5, 1.5),
                (4.5, 0.5),
                (4.5, 2.5),
                (5.5, 1.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.Y, False),
            Basis.X,
            False,
            [
                (0.5, 1.5),
                (1.5, 0.5),
                (1.5, 2.5),
                (2.5, 1.5),
                (3.5, 0.5),
                (3.5, 2.5),
                (4.5, 1.5),
                (5.5, 0.5),
                (5.5, 2.5),
            ],
        ),
        (
            SignedDirection3D(Direction3D.Y, False),
            Basis.X,
            True,
            [
                (0.5, 1.5),
                (1.5, 0.5),
                (1.5, 2.5),
                (2.5, 1.5),
                (3.5, 0.5),
                (3.5, 2.5),
                (4.5, 1.5),
                (5.5, 0.5),
                (5.5, 2.5),
            ],
        ),
    ],
)
def test_get_bottom_stabilizer_cube_qubits(
    connect_to: SignedDirection3D,
    stabilizer_basis: Basis,
    spatial_hadamard: bool,
    expected: list[tuple[float, float]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = sorted(
        _get_bottom_stabilizer_cube_qubits(
            shape, connect_to, stabilizer_basis, spatial_hadamard
        )
    )
    assert coords == expected


@pytest.mark.parametrize("k", (1, 2, 10))
@pytest.mark.parametrize("basis", (Basis.X, Basis.Z))
def test_get_bottom_stabilizer_spatial_cube_qubits(k: int, basis: Basis) -> None:
    w = 2 * k + 2
    shape = PlaquetteShape2D(w, w)
    coords = set(_get_bottom_stabilizer_spatial_cube_qubits(shape, basis))
    assert len(coords) == w**2 // 2
    assert all((cs[0] + cs[1]) % 2 == (basis == Basis.Z) for cs in coords)


@pytest.mark.parametrize(
    "arms, observabel_basis, expected",
    [
        (SpatialArms.LEFT | SpatialArms.UP, Basis.X, {(0, 2), (1, 2), (2, 0), (2, 1)}),
        (
            SpatialArms.LEFT | SpatialArms.UP,
            Basis.Z,
            {(0, 2), (1, 2), (2, 0), (2, 1), (2, 2)},
        ),
        (
            SpatialArms.LEFT | SpatialArms.DOWN,
            Basis.Z,
            {(0, 2), (1, 2), (2, 2), (2, 3), (2, 4)},
        ),
        (
            SpatialArms.UP | SpatialArms.RIGHT,
            Basis.X,
            {(2, 1), (2, 0), (4, 2), (2, 2), (3, 2)},
        ),
        (
            SpatialArms.DOWN | SpatialArms.RIGHT,
            Basis.X,
            {(2, 3), (2, 4), (4, 2), (3, 2)},
        ),
        (
            SpatialArms.LEFT | SpatialArms.RIGHT,
            Basis.Z,
            {(0, 2), (1, 2), (2, 2), (3, 2), (4, 2)},
        ),
        (
            SpatialArms.UP | SpatialArms.DOWN,
            Basis.Z,
            {(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)},
        ),
    ],
)
def test_get_top_readout_spatial_cube_qubits(
    arms: SpatialArms,
    observabel_basis: Basis,
    expected: set[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(4, 4)
    coords = set(_get_top_readout_spatial_cube_qubits(shape, arms, observabel_basis))
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
