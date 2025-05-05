from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.observables.fixed_parity_builder import _get_top_readout_cube_qubits
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.pipe import Pipe
from tqec.utils.enums import Basis, Orientation
from tqec.utils.position import Direction3D, PlaquetteShape2D, SignedDirection3D


def _get_bottom_stabilizer_cube_qubits(
    cube_shape: PlaquetteShape2D, connect_to: SignedDirection3D, stabilizer_basis: Basis
) -> list[tuple[float, float]]:
    stabilizers: list[tuple[float, float]] = []
    xy_sum_parity = 0 if stabilizer_basis == Basis.Z else 1
    # We calculate the qubits for the connect_to=SignedDirection3D(Direction3D.X, True) case
    # and rotate to get the correct orientation.
    for i in range(cube_shape.x // 2, cube_shape.x):
        for j in range(cube_shape.y):
            if (i + j) % 2 != xy_sum_parity:
                continue
            x = i + 0.5
            y = j + 0.5
            # reflect the coordinates along the middle line of the cube
            # if the direction is along Y to preserve the checkerboard parity
            if connect_to.direction == Direction3D.Y:
                y = cube_shape.y - y
            stabilizers.append((x, y))

    # rotate all coordinates around the block center:
    # rx = cx + a * (x - cx) - b * (y - cy)
    # ry = cy + b * (x - cx) + a * (y - cy)
    # in which (cx, cy) is the center of the block, a = cos(theta), b = sin(theta)
    # and theta is the angle of rotation.
    a, b = 1, 0
    match connect_to:
        case SignedDirection3D(Direction3D.X, False):
            a, b = -1, 0
        case SignedDirection3D(Direction3D.Y, True):
            a, b = 0, 1
        case SignedDirection3D(Direction3D.Y, False):
            a, b = 0, -1
        case _:
            pass
    cx, cy = cube_shape.x // 2, cube_shape.y // 2
    return [
        (
            cx + a * (x - cx) - b * (y - cy),
            cy + b * (x - cx) + a * (y - cy),
        )
        for x, y in stabilizers
    ]


def _get_top_readout_pipe_qubits(
    u_shape: PlaquetteShape2D, pipe: Pipe
) -> list[tuple[int, int]]:
    direction = pipe.direction
    assert direction != Direction3D.Z
    if direction == Direction3D.X:
        return [(u_shape.x, u_shape.y // 2)]
    else:
        return [(u_shape.x // 2, u_shape.y)]


def _get_top_readout_spatial_cube_qubits(
    cube_shape: PlaquetteShape2D, arms: SpatialArms, observable_basis: Basis
) -> list[tuple[int, int]]:
    assert len(arms) == 2
    half_x, half_y = cube_shape.x // 2, cube_shape.y // 2

    if arms == SpatialArms.LEFT | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(1, cube_shape.x)]
    elif arms == SpatialArms.UP | SpatialArms.DOWN:
        return [(half_x, y) for y in range(1, cube_shape.y)]
    elif arms == SpatialArms.LEFT | SpatialArms.UP:
        qubits = [(x, half_y) for x in range(1, half_x)] + [
            (half_x, y) for y in range(1, half_y)
        ]
        if observable_basis == Basis.Z:
            qubits.append((half_x, half_y))
        return qubits
    elif arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        qubits = [(x, half_y) for x in range(cube_shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(cube_shape.y - 1, half_y, -1)
        ]
        if observable_basis == Basis.Z:
            qubits.append((half_x, half_y))
        return qubits
    elif arms == SpatialArms.UP | SpatialArms.RIGHT:
        qubits = [(x, half_y) for x in range(cube_shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(1, half_y)
        ]
        if observable_basis == Basis.X:
            qubits.append((half_x, half_y))
        return qubits
    else:  # arms == SpatialArms.LEFT | SpatialArms.DOWN:
        qubits = [(x, half_y) for x in range(1, half_x)] + [
            (half_x, y) for y in range(cube_shape.y - 1, half_y, -1)
        ]
        if observable_basis == Basis.X:
            qubits.append((half_x, half_y))
        return qubits


def _get_bottom_stabilizer_spatial_cube_qubits(
    cube_shape: PlaquetteShape2D, stabilizer_basis: Basis
) -> list[tuple[float, float]]:
    xy_sum_parity = 0 if stabilizer_basis == Basis.Z else 1
    return [
        (i + 0.5, j + 0.5)
        for i in range(cube_shape.x)
        for j in range(cube_shape.y)
        if (i + j) % 2 == xy_sum_parity
    ]


def _get_temporal_hadamard_includes_qubits(
    shape: PlaquetteShape2D, observable_basis: Basis, z_orientation: Orientation
) -> list[tuple[float, float]]:
    # observable is horizontal
    if (observable_basis == Basis.X) ^ (z_orientation == Orientation.HORIZONTAL):
        if (shape.x % 4 == 0) ^ (observable_basis == Basis.Z):
            return [(shape.x - 0.5, shape.y // 2 + 0.5)]
        return []
    # observable is vertical
    if (shape.y % 4 == 0) ^ (observable_basis == Basis.Z):
        return [(shape.x // 2 + 0.5, shape.y - 0.5)]
    return []


FIXED_BULK_OBSERVABLE_BUILDER = ObservableBuilder(
    _get_top_readout_cube_qubits,
    _get_top_readout_spatial_cube_qubits,
    _get_top_readout_pipe_qubits,
    _get_bottom_stabilizer_cube_qubits,
    _get_bottom_stabilizer_spatial_cube_qubits,
    _get_temporal_hadamard_includes_qubits,
)
