from collections.abc import Sequence

from tqec.compile.observables.abstract_observable import CubeWithArms, PipeWithArms
from tqec.compile.observables.builder import Coordinates2D, ObservableBuilder
from tqec.compile.observables.fixed_bulk_builder import build_regular_cube_top_readout_qubits
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Orientation
from tqec.utils.position import Direction3D, PlaquetteShape2D, SignedDirection3D


def build_spatial_cube_top_readout_qubits(
    shape: PlaquetteShape2D, arms: SpatialArms
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates for a straight or bent middle line of the top face of a spatial
    cube.
    """
    assert len(arms) == 2
    half_x, half_y = shape.x // 2, shape.y // 2

    if arms == SpatialArms.LEFT | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(1, shape.x)]
    elif arms == SpatialArms.UP | SpatialArms.DOWN:
        return [(half_x, y) for y in range(1, shape.y)]
    elif arms == SpatialArms.LEFT | SpatialArms.UP:
        return [(x, half_y) for x in range(1, half_x)] + [(half_x, y) for y in range(1, half_y)]
    elif arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(shape.y - 1, half_y, -1)
        ]
    elif arms == SpatialArms.UP | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(1, half_y + 1)
        ]
    # arms == SpatialArms.LEFT | SpatialArms.DOWN:
    return [(x, half_y) for x in range(1, half_x + 1)] + [
        (half_x, y) for y in range(shape.y - 1, half_y, -1)
    ]


def build_cube_top_readout_qubits(
    shape: PlaquetteShape2D, cube: CubeWithArms
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates whose measurements will be included in the observable on the top
    face of a cube.
    """
    if not cube.cube.is_spatial:
        kind = cube.cube.kind
        assert isinstance(kind, ZXCube)
        # Determine the middle line orientation based on the cube kind.
        # Since the basis of the top face decides the measurement basis of the data
        # qubits, i.e. the logical operator basis. We only need to find the spatial
        # boundaries that the logical operator can be attached to.
        obs_orientation = Orientation.VERTICAL if kind.y == kind.z else Orientation.HORIZONTAL
        return build_regular_cube_top_readout_qubits(shape, obs_orientation)
    return build_spatial_cube_top_readout_qubits(shape, cube.arms)


def _extended_stabilizers_used(
    pipe: PipeWithArms,
) -> bool:
    if pipe.pipe.direction == Direction3D.X:
        return False
    u_arms, v_arms = pipe.cube_arms
    return u_arms.has_spatial_arm_in_both_dimensions ^ v_arms.has_spatial_arm_in_both_dimensions


def _build_pipe_top_readout_qubits_impl(
    shape: PlaquetteShape2D, direction: Direction3D, extended_stabilizers_used: bool
) -> Sequence[Coordinates2D]:
    assert direction != Direction3D.Z
    if direction == Direction3D.X:
        return [(shape.x, shape.y // 2)]
    # Extended stabilizers at pipe do not have qubits that need to be include
    # in the observable.
    if extended_stabilizers_used:
        return []
    return [(shape.x // 2, shape.y)]


def build_pipe_top_readout_qubits(
    shape: PlaquetteShape2D, pipe: PipeWithArms
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates whose measurements will be included in the observable on the top
    face of a pipe.
    """
    return _build_pipe_top_readout_qubits_impl(
        shape, pipe.pipe.direction, _extended_stabilizers_used(pipe)
    )


def build_regular_cube_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D,
    connect_to: SignedDirection3D,
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates who will be included in the observable spanning
    half of the bottom face of a regular cube.
    """
    stabilizers: list[tuple[float, float]] = []
    # We calculate the qubits for the connect_to=SignedDirection3D(Direction3D.X, True) case
    # and rotate to get the correct orientation.
    for i in range(shape.x // 2):
        x = shape.x - i - 0.5
        for j in range(shape.y // 2):
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
    cx, cy = shape.x // 2, shape.y // 2
    return [
        (
            cx + a * (x - cx) - b * (y - cy),
            cy + b * (x - cx) + a * (y - cy),
        )
        for x, y in stabilizers
    ]


def build_spatial_cube_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D,
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates who will be included in the observable spanning
    the bottom face of a single spatial cube.
    """
    return [(i + 0.5, j + 0.5) for i in range(shape.x) for j in range(shape.y) if (i + j) % 2 == 0]


def build_connected_spatial_cube_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D,
    arms: SpatialArms,
    connect_to: SignedDirection3D,
    extended_stabilizers_used: bool,
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates who will be included in the observable spanning
    the bottom face of a spatial cube connected to pipes.
    """
    max_y = (
        shape.y - 1
        if extended_stabilizers_used and connect_to == SignedDirection3D(Direction3D.Y, True)
        else shape.y
    )
    bulk_parity = 1 if arms in [SpatialArms.UP, SpatialArms.DOWN] else 0
    return [
        (i + 0.5, j + 0.5)
        for i in range(shape.x)
        for j in range(max_y)
        if (i + j) % 2 == bulk_parity
    ]


def build_pipe_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D, pipe: PipeWithArms
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates who will be included in the observable on the
    bottom face of a pipe.

    It includes the bottom stabilizers of the connected cubes.

    """
    direction = pipe.pipe.direction
    extended_stabilizers_used = _extended_stabilizers_used(pipe)

    qubits: list[Coordinates2D] = []
    for cube, arms in zip(pipe.pipe, pipe.cube_arms):
        kind = cube.kind
        assert isinstance(kind, ZXCube)
        is_u = cube == pipe.pipe.u
        connect_to = SignedDirection3D(direction, is_u)
        if cube.is_spatial:
            stabilizers = build_connected_spatial_cube_bottom_stabilizer_qubits(
                shape, arms, connect_to, extended_stabilizers_used
            )
        else:
            stabilizers = build_regular_cube_bottom_stabilizer_qubits(shape, connect_to)
        # the local coordinates is of cube u, therefore, we need to shift the coordinates
        # of the stabilizers within cube v
        if not is_u:
            stabilizers = [
                (
                    s[0] + shape.x if direction == Direction3D.X else s[0],
                    s[1] + shape.y if direction == Direction3D.Y else s[1],
                )
                for s in stabilizers
            ]
        qubits.extend(stabilizers)
    return qubits


FIXED_BOUNDARY_OBSERVABLE_BUILDER = ObservableBuilder(
    cube_top_readouts_builder=build_cube_top_readout_qubits,
    pipe_top_readouts_builder=build_pipe_top_readout_qubits,
    cube_bottom_stabilizers_builder=lambda shape, cube: build_spatial_cube_bottom_stabilizer_qubits(
        shape
    ),
    pipe_bottom_stabilizers_builder=build_pipe_bottom_stabilizer_qubits,
    pipe_temporal_hadamard_builder=lambda shape, pipe: [],
)
