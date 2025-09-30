from collections.abc import Sequence

from tqec.compile.observables.abstract_observable import (
    CubeWithArms,
    PipeWithArms,
    PipeWithObservableBasis,
)
from tqec.compile.observables.builder import Coordinates2D, ObservableBuilder
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.utils.enums import Basis, Orientation
from tqec.utils.position import Direction3D, PlaquetteShape2D, SignedDirection3D


def build_regular_cube_top_readout_qubits(
    shape: PlaquetteShape2D, observable_orientation: Orientation
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates for the middle line of the top face of a regular cube."""
    if observable_orientation == Orientation.HORIZONTAL:
        return [(x, shape.y // 2) for x in range(1, shape.x)]
    return [(shape.x // 2, y) for y in range(1, shape.y)]


def build_spatial_cube_top_readout_qubits(
    shape: PlaquetteShape2D, arms: SpatialArms, observable_basis: Basis
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates for a straight or bent middle line of the top face of a spatial
    cube.
    """
    assert len(arms) == 2
    half_x, half_y = shape.x // 2, shape.y // 2

    if arms == SpatialArms.LEFT | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(1, shape.x)]
    if arms == SpatialArms.UP | SpatialArms.DOWN:
        return [(half_x, y) for y in range(1, shape.y)]
    if arms == SpatialArms.LEFT | SpatialArms.UP:
        qubits = [(x, half_y) for x in range(1, half_x)] + [(half_x, y) for y in range(1, half_y)]
        if observable_basis == Basis.Z:
            qubits.append((half_x, half_y))
        return qubits
    if arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        qubits = [(x, half_y) for x in range(shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(shape.y - 1, half_y, -1)
        ]
        if observable_basis == Basis.Z:
            qubits.append((half_x, half_y))
        return qubits
    if arms == SpatialArms.UP | SpatialArms.RIGHT:
        qubits = [(x, half_y) for x in range(shape.x - 1, half_x, -1)] + [
            (half_x, y) for y in range(1, half_y)
        ]
        if observable_basis == Basis.X:
            qubits.append((half_x, half_y))
        return qubits
    # arms == SpatialArms.LEFT | SpatialArms.DOWN:
    qubits = [(x, half_y) for x in range(1, half_x)] + [
        (half_x, y) for y in range(shape.y - 1, half_y, -1)
    ]
    if observable_basis == Basis.X:
        qubits.append((half_x, half_y))
    return qubits


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
    kind = cube.cube.kind
    assert isinstance(kind, ZXCube)
    observable_basis = kind.z
    return build_spatial_cube_top_readout_qubits(shape, cube.arms, observable_basis)


def build_pipe_top_readout_qubits(
    shape: PlaquetteShape2D, direction: Direction3D
) -> Sequence[Coordinates2D]:
    """Build the qubit coordinates whose measurements will be included in the observable on the top
    face of a pipe.
    """
    assert direction != Direction3D.Z
    if direction == Direction3D.X:
        return [(shape.x, shape.y // 2)]
    return [(shape.x // 2, shape.y)]


def build_regular_cube_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D,
    connect_to: SignedDirection3D,
    stabilizer_basis: Basis,
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates that will be included in the observable
    spanning half of the bottom face of a regular cube.
    """
    stabilizers: list[tuple[float, float]] = []
    xy_sum_parity = 0 if stabilizer_basis == Basis.Z else 1
    # We calculate the qubits for the connect_to=SignedDirection3D(Direction3D.X, True) case
    # and rotate to get the correct orientation.
    for i in range(shape.x // 2, shape.x):
        for j in range(shape.y):
            if (i + j) % 2 != xy_sum_parity:
                continue
            x = i + 0.5
            y = j + 0.5
            # reflect the coordinates along the middle line of the cube
            # if the direction is along Y to preserve the checkerboard parity
            if connect_to.direction == Direction3D.Y:
                y = shape.y - y
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
    shape: PlaquetteShape2D, stabilizer_basis: Basis
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates that will be included in the observable
    spanning the bottom face of a spatial cube.
    """
    xy_sum_parity = 0 if stabilizer_basis == Basis.Z else 1
    return [
        (i + 0.5, j + 0.5)
        for i in range(shape.x)
        for j in range(shape.y)
        if (i + j) % 2 == xy_sum_parity
    ]


def build_cube_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D, cube: CubeWithArms
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates that will be included in the observable on the
    bottom face of a cube.
    """
    assert cube.cube.is_spatial
    kind = cube.cube.kind
    assert isinstance(kind, ZXCube)
    return build_spatial_cube_bottom_stabilizer_qubits(shape, kind.x)


def build_pipe_bottom_stabilizer_qubits(
    shape: PlaquetteShape2D, pipe: PipeWithArms
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates that will be included in the observable on the
    bottom face of a pipe.

    It includes the bottom stabilizers of the connected cubes.

    """
    direction = pipe.pipe.direction

    qubits: list[Coordinates2D] = []
    for cube in pipe.pipe:
        kind = cube.kind
        assert isinstance(kind, ZXCube)
        is_u = cube == pipe.pipe.u
        if cube.is_spatial:
            stabilizers = build_spatial_cube_bottom_stabilizer_qubits(shape, kind.x)
        else:
            connect_to = SignedDirection3D(direction, is_u)
            stabilizer_basis = kind.get_basis_along(Direction3D(1 - direction.value))
            stabilizers = build_regular_cube_bottom_stabilizer_qubits(
                shape, connect_to, stabilizer_basis
            )
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


def _build_pipe_temporal_hadamard_qubits_impl(
    shape: PlaquetteShape2D, observable_basis: Basis, z_orientation: Orientation
) -> Sequence[Coordinates2D]:
    # observable is horizontal
    if (observable_basis == Basis.X) ^ (z_orientation == Orientation.HORIZONTAL):
        if (shape.x % 4 == 0) ^ (observable_basis == Basis.Z):
            return [(shape.x - 0.5, shape.y // 2 + 0.5)]
        return []
    # observable is vertical
    if (shape.y % 4 == 0) ^ (observable_basis == Basis.Z):
        return [(shape.x // 2 + 0.5, shape.y - 0.5)]
    return []


def build_pipe_temporal_hadamard_qubits(
    shape: PlaquetteShape2D, pipe: PipeWithObservableBasis
) -> Sequence[Coordinates2D]:
    """Build the stabilizer measurement coordinates that will be included in the observable at the
    realignment layer of a temporal Hadamard pipe.
    """
    pipe_kind = pipe.pipe.kind
    observable_basis = pipe.observable_basis
    z_orientation = (
        Orientation.VERTICAL
        if pipe_kind.get_basis_along(Direction3D.Y) == Basis.Z
        else Orientation.HORIZONTAL
    )
    return _build_pipe_temporal_hadamard_qubits_impl(shape, observable_basis, z_orientation)


FIXED_BULK_OBSERVABLE_BUILDER = ObservableBuilder(
    cube_top_readouts_builder=build_cube_top_readout_qubits,
    pipe_top_readouts_builder=lambda shape, pipe: build_pipe_top_readout_qubits(
        shape, pipe.pipe.direction
    ),
    cube_bottom_stabilizers_builder=build_cube_bottom_stabilizer_qubits,
    pipe_bottom_stabilizers_builder=build_pipe_bottom_stabilizer_qubits,
    pipe_temporal_hadamard_builder=build_pipe_temporal_hadamard_qubits,
)
