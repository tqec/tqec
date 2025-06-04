import pytest

from tqec.compile.observables.fixed_bulk_builder import (
    _get_bottom_stabilizer_cube_qubits,
    _get_bottom_stabilizer_spatial_cube_qubits,
    _get_top_readout_spatial_cube_qubits,
    _get_temporal_hadamard_includes_qubits,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.utils.enums import Basis, Orientation
from tqec.utils.position import (
    Direction3D,
    PlaquetteShape2D,
    SignedDirection3D,
)


@pytest.mark.parametrize(
    "connect_to, stabilizer_basis, expected",
    [
        (
            SignedDirection3D(Direction3D.X, True),
            Basis.Z,
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
            SignedDirection3D(Direction3D.X, False),
            Basis.Z,
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
            SignedDirection3D(Direction3D.Y, False),
            Basis.Z,
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
    expected: list[tuple[float, float]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = sorted(_get_bottom_stabilizer_cube_qubits(shape, connect_to, stabilizer_basis))
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
        (SpatialArms.LEFT | SpatialArms.UP, Basis.X, {(1, 2), (2, 1)}),
        (
            SpatialArms.LEFT | SpatialArms.UP,
            Basis.Z,
            {(1, 2), (2, 1), (2, 2)},
        ),
        (
            SpatialArms.LEFT | SpatialArms.DOWN,
            Basis.Z,
            {(1, 2), (2, 3)},
        ),
        (
            SpatialArms.UP | SpatialArms.RIGHT,
            Basis.X,
            {(2, 1), (2, 2), (3, 2)},
        ),
        (
            SpatialArms.DOWN | SpatialArms.RIGHT,
            Basis.X,
            {(2, 3), (3, 2)},
        ),
        (
            SpatialArms.LEFT | SpatialArms.RIGHT,
            Basis.Z,
            {(1, 2), (2, 2), (3, 2)},
        ),
        (
            SpatialArms.UP | SpatialArms.DOWN,
            Basis.Z,
            {(2, 1), (2, 2), (2, 3)},
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


@pytest.mark.parametrize(
    "k, obs_basis, z_orientation, expected",
    [
        (1, Basis.Z, Orientation.VERTICAL, set()),
        (1, Basis.Z, Orientation.HORIZONTAL, set()),
        (1, Basis.X, Orientation.VERTICAL, {(3.5, 2.5)}),
        (1, Basis.X, Orientation.HORIZONTAL, {(2.5, 3.5)}),
        (2, Basis.Z, Orientation.VERTICAL, {(3.5, 5.5)}),
        (2, Basis.Z, Orientation.HORIZONTAL, {(5.5, 3.5)}),
        (2, Basis.X, Orientation.VERTICAL, set()),
        (2, Basis.X, Orientation.HORIZONTAL, set()),
    ],
)
def test_get_temporal_hadamard_includes(
    k: int,
    obs_basis: Basis,
    z_orientation: Orientation,
    expected: set[tuple[float, float]],
) -> None:
    shape = PlaquetteShape2D(2 * k + 2, 2 * k + 2)
    coords = set(_get_temporal_hadamard_includes_qubits(shape, obs_basis, z_orientation))
    assert coords == expected
