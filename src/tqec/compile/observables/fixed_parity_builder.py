from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.utils.position import Direction3D, PlaquetteShape2D, SignedDirection3D


def _get_top_readout_cube_qubits(
    shape: PlaquetteShape2D, cube_kind: ZXCube
) -> list[tuple[int, int]]:
    # Determine the middle line orientation based on the cube kind.
    # Since the basis of the top face decides the measurement basis of the data
    # qubits, i.e. the logical operator basis. We only need to find the spatial
    # boundaries that the logical operator can be attached to.
    obs_orientation = Direction3D(int(cube_kind.y == cube_kind.z))
    if obs_orientation == Direction3D.X:
        return [(x, shape.y // 2) for x in range(1, shape.x)]
    else:
        return [(shape.x // 2, y) for y in range(1, shape.y)]


def _get_top_readout_pipe_qubits(
    u_shape: PlaquetteShape2D, connect_to: Direction3D
) -> list[tuple[int, int]]:
    assert connect_to != Direction3D.Z
    if connect_to == Direction3D.X:
        return [(u_shape.x, u_shape.y // 2)]
    else:
        return [(u_shape.x // 2, u_shape.y)]


def _get_bottom_stabilizer_cube_qubits(
    cube_shape: PlaquetteShape2D, connect_to: SignedDirection3D
) -> list[tuple[float, float]]:
    stabilizers: list[tuple[float, float]] = []
    # We calculate the qubits for the connect_to=SignedDirection3D(Direction3D.X, True) case
    # and rotate to get the correct orientation.
    for i in range(cube_shape.x // 2):
        x = cube_shape.x - i - 0.5
        for j in range(cube_shape.y // 2):
            y = (1 - i % 2) + 2 * j + 0.5
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


def _get_top_readout_spatial_cube_qubits(
    cube_shape: PlaquetteShape2D, arms: SpatialArms
) -> list[tuple[int, int]]:
    assert len(arms) == 2
    half_x, half_y = cube_shape.x // 2, cube_shape.y // 2

    if arms == SpatialArms.LEFT | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(1, cube_shape.x)]
    elif arms == SpatialArms.UP | SpatialArms.DOWN:
        return [(half_x, y) for y in range(1, cube_shape.y)]
    elif arms == SpatialArms.LEFT | SpatialArms.UP:
        return [(x, half_y) for x in range(1, half_x)] + [
            (half_x, y) for y in range(1, half_y)
        ]
    elif arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(cube_shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(cube_shape.y - 1, half_y, -1)
        ]
    elif arms == SpatialArms.UP | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(cube_shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(1, half_y + 1)
        ]
    else:  # arms == SpatialArms.LEFT | SpatialArms.DOWN:
        return [(x, half_y) for x in range(1, half_x + 1)] + [
            (half_x, y) for y in range(cube_shape.y - 1, half_y, -1)
        ]


def _get_bottom_stabilizer_spatial_cube_qubits(
    cube_shape: PlaquetteShape2D,
) -> list[tuple[float, float]]:
    return [
        (i + 0.5, j + 0.5)
        for i in range(cube_shape.x)
        for j in range(cube_shape.y)
        if (i + j) % 2 == 0
    ]


FIXED_PARITY_OBSERVABLE_BUILDER = ObservableBuilder(
    _get_top_readout_cube_qubits,
    lambda shape, arms, _: _get_top_readout_spatial_cube_qubits(shape, arms),
    _get_top_readout_pipe_qubits,
    lambda shape, connect, _: _get_bottom_stabilizer_cube_qubits(shape, connect),
    lambda shape, _: _get_bottom_stabilizer_spatial_cube_qubits(shape),
)
