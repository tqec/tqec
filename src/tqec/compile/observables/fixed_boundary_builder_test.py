import pytest

from tqec.compile.observables.fixed_boundary_builder import (
    build_connected_spatial_cube_bottom_stabilizer_qubits,
    build_pipe_top_readout_qubits_impl,
    build_regular_cube_bottom_stabilizer_qubits,
    build_spatial_cube_bottom_stabilizer_qubits,
    build_spatial_cube_top_readout_qubits,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.utils.position import (
    Direction3D,
    PlaquetteShape2D,
    SignedDirection3D,
)


@pytest.mark.parametrize(
    "direction, extended_stabilizers_used, expected",
    [
        (Direction3D.X, False, [(6, 3)]),
        (Direction3D.Y, False, [(3, 6)]),
        (Direction3D.X, True, [(6, 3)]),
        (Direction3D.Y, True, []),
    ],
)
def test_build_pipe_top_readout_qubits_impl(
    direction: Direction3D,
    extended_stabilizers_used: bool,
    expected: list[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = build_pipe_top_readout_qubits_impl(shape, direction, extended_stabilizers_used)
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
def test_build_regular_cube_bottom_stabilizer_qubits(
    connect_to: SignedDirection3D,
    expected: set[tuple[float, float]],
) -> None:
    shape = PlaquetteShape2D(6, 6)
    coords = set(build_regular_cube_bottom_stabilizer_qubits(shape, connect_to))
    assert coords == expected


@pytest.mark.parametrize("k", (1, 2, 10))
def test_build_spatial_cube_bottom_stabilizer_qubits(k: int) -> None:
    w = 2 * k + 2
    shape = PlaquetteShape2D(w, w)
    coords = set(build_spatial_cube_bottom_stabilizer_qubits(shape))
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
def test_build_spatial_cube_top_readout_qubits(
    arms: SpatialArms,
    expected: set[tuple[int, int]],
) -> None:
    shape = PlaquetteShape2D(4, 4)
    coords = set(build_spatial_cube_top_readout_qubits(shape, arms))
    assert coords == expected


@pytest.mark.parametrize("k", (1, 2, 10))
def test_build_connected_spatial_cube_bottom_stabilizer_qubits(k: int) -> None:
    w = 2 * k + 2
    shape = PlaquetteShape2D(w, w)
    arms = SpatialArms.UP
    connect_to = SignedDirection3D.from_string("+Y")
    coords = set(
        build_connected_spatial_cube_bottom_stabilizer_qubits(shape, arms, connect_to, True)
    )
    assert coords == {
        (i + 0.5, j + 0.5) for i in range(shape.x) for j in range(w - 1) if (i + j) % 2 == 1
    }
