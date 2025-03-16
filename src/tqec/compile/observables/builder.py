"""Provides helper functions to add observables to circuits."""

from dataclasses import dataclass
from typing import Iterable

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.templates.layout import LayoutTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.position import (
    Direction3D,
    PlaquetteShape2D,
    Position3D,
    SignedDirection3D,
)
from tqec.utils.scale import round_or_fail


@dataclass(frozen=True)
class Observable:
    """Logical observable consisting of a list of measurements."""

    observable_index: int
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "OBSERVABLE_INCLUDE",
            [stim.target_rec(offset) for offset in self.measurement_offsets],
            [self.observable_index],
        )


def inplace_add_observable(
    k: int,
    circuits: list[list[ScheduledCircuit]],
    template_slices: list[LayoutTemplate],
    abstract_observable: AbstractObservable,
    observable_index: int,
) -> None:
    """Inplace add the observable components to the circuits.

    This functions takes the compiled ``AbstractObservable`` and calculates
    the measurement coordinates in it. Then it collects the measurements
    into logical observable and adds them in the correct locations in the
    sliced circuits.

    Args:
        k: The scaling factor of the block.
        circuits: The circuits to add the observables to. The circuits are
            grouped by time slices and layers. The outer list represents the
            time slices and the inner list represents the layers.
        template_slices: The layout templates of the blocks indexed by the
            time steps.
        abstract_observable: The abstract observable to add to the circuits.
        observable_index: The index of the observable.
    """
    for z in range(len(circuits)):
        for at_bottom in [True, False]:
            obs_qubits = compute_observable_qubits(
                k, abstract_observable, template_slices[z], z, at_bottom
            )
            if not obs_qubits:
                continue
            circuit = circuits[z][0] if at_bottom else circuits[z][-1]
            obs = get_observable_with_circuit(circuit, observable_index, obs_qubits)
            obs_instruction = obs.to_instruction()
            circuit.append_annotation(obs_instruction)


def compute_observable_qubits(
    k: int,
    observable: AbstractObservable,
    template: LayoutTemplate,
    z: int,
    at_bottom: bool,
) -> set[GridQubit]:
    obs_slice = observable.slice_at_z(z)
    obs_qubits: set[GridQubit] = set()

    def _block_shape(k: int) -> PlaquetteShape2D:
        return template.element_shape(k)

    def _transform_and_collect(
        pos: Position3D,
        qubits: Iterable[tuple[float, float] | tuple[int, int]],
    ) -> None:
        obs_qubits.update(
            _transform_coords_into_grid(template, q, pos, k) for q in qubits
        )

    # The stabilizer measurements that will be added to the end of the first layer of circuits at z.
    if at_bottom:
        for pipe in obs_slice.bottom_stabilizer_pipes:
            for cube in pipe:
                # the stabilizer measurements included in spatial cubes will be
                # handled later
                if cube.is_spatial:
                    continue
                _transform_and_collect(
                    cube.position,
                    _get_bottom_stabilizer_cube_qubits(
                        _block_shape(k),
                        SignedDirection3D(pipe.direction, cube == pipe.u),
                    ),
                )
        for cube in obs_slice.bottom_stabilizer_spatial_cubes:
            _transform_and_collect(
                cube.position,
                _get_bottom_stabilizer_spatial_cube_qubits(_block_shape(k)),
            )
        return obs_qubits

    # The data qubit readouts that will be added to the end of the last layer of circuits at z.
    for pipe in obs_slice.top_readout_pipes:
        _transform_and_collect(
            pipe.u.position,
            _get_top_readout_pipe_qubits(_block_shape(k), pipe.direction),
        )
    for cube in obs_slice.top_readout_cubes:
        assert isinstance(cube.kind, ZXCube)
        _transform_and_collect(
            cube.position,
            _get_top_readout_cube_qubits(_block_shape(k), cube.kind),
        )
    for cube, arms in obs_slice.top_readout_spatial_cubes:
        _transform_and_collect(
            cube.position,
            _get_top_readout_spatial_cube_qubits(_block_shape(k), arms),
        )
    return obs_qubits


def get_observable_with_circuit(
    circuit: ScheduledCircuit,
    observable_index: int,
    observable_qubits: set[GridQubit],
) -> Observable:
    measurement_records = MeasurementRecordsMap.from_scheduled_circuit(circuit)
    measurement_offsets = [
        measurement_records[q][-1]
        for q in observable_qubits
        # Filter out those qubits that are not in the circuit.
        # This is required because the current implementation of
        # bottom stabilizer calculation for spatial cubes
        # may include qubits that are not in the circuit, as
        # intended for simplifying the calculation.
        # This has the risk of not catching the coordinate
        # calculation errors but the tests for determinism
        # and code distance should catch them.
        if q in measurement_records
    ]
    return Observable(observable_index, measurement_offsets)


def _transform_coords_into_grid(
    template: LayoutTemplate,
    local_coords: tuple[float, float] | tuple[int, int],
    block_position: Position3D,
    k: int,
) -> GridQubit:
    """Transform local coordinates at a block to the global coordinates in the
    circuit.

    When calculating the coordinates of the measurement qubits, we use a local coordinate system
    in the individual blocks. The top-left corner of the block starts at (0, 0) and each column
    is separated by 0.5. That is, all the data qubits are placed at the integer coordinates while
    all the measurement qubits are placed at the half-integer coordinates.

    This convention helps reducing the number of arguments needed to pass around and simplifies
    the calculation of the qubit coordinates. The global coordinates are calculated by offsetting
    the local coordinates by the global position of the block and accounting for the
    ``Template.default_increments``.
    """
    block_shape = template.element_shape(k)
    template_increments = template.get_increments()
    width = block_shape.x * template_increments.x
    height = block_shape.y * template_increments.y
    x = block_position.x * width + round_or_fail(
        (local_coords[0] - 0.5) * template_increments.x
    )
    y = block_position.y * height + round_or_fail(
        (local_coords[1] - 0.5) * template_increments.y
    )
    return GridQubit(x, y)


def _get_top_readout_cube_qubits(
    shape: PlaquetteShape2D, cube_kind: ZXCube
) -> list[tuple[int, int]]:
    """The data qubits on the middle line of the cube will be read out and
    included in the logical observable.

    This function calculates the coordinates of these data qubits in the
    local coordinate system.
    """
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
    """The top line at a pipe is actually a single data qubits at the interface
    of the two connected cubes.

    The measurement result of this qubit will be included in the logical
    observable. This function calculates the coordinates of this data
    qubit in the local coordinate system of the cube at the head of the
    pipe.
    """
    assert connect_to != Direction3D.Z
    if connect_to == Direction3D.X:
        return [(u_shape.x, u_shape.y // 2)]
    else:
        return [(u_shape.x // 2, u_shape.y)]


def _get_bottom_stabilizer_cube_qubits(
    cube_shape: PlaquetteShape2D, connect_to: SignedDirection3D
) -> list[tuple[float, float]]:
    """The stabilizer measurements at the bottom of the cube will be included
    in the logical observable. Note that only half of the stabilizers in the
    basis of the boundary that the cube connects to will be included. Each cube
    is only responsible for the stabilizer measurements within its bounding
    box. Collecting the measurements from the two cubes connected by the pipe
    will give the full stabilizer measurements, of which the product determines
    the parity of the logical operators.

    This function calculates the coordinates of the measurement qubits
    in the local coordinate system of the cube.
    """
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
    """The data qubits at the spatial cubes will be read out and included in
    the logical observable.

    This function calculates the coordinates of the data qubits in the
    local coordinate system of the cube based on which arms the
    correlation surface touches.
    """
    assert len(arms) == 2
    half_x, half_y = cube_shape.x // 2, cube_shape.y // 2

    if arms == SpatialArms.LEFT | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(cube_shape.x + 1)]
    elif arms == SpatialArms.UP | SpatialArms.DOWN:
        return [(half_x, y) for y in range(cube_shape.y + 1)]
    elif arms == SpatialArms.LEFT | SpatialArms.UP:
        return [(x, half_y) for x in range(half_x)] + [
            (half_x, y) for y in range(half_y)
        ]
    elif arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(cube_shape.x, half_x, -1)] + [
            (half_x, y) for y in range(cube_shape.y, half_y, -1)
        ]
    elif arms == SpatialArms.UP | SpatialArms.RIGHT:
        return [(x, half_y) for x in range(cube_shape.x, half_x, -1)] + [
            (half_x, y) for y in range(half_y + 1)
        ]
    else:  # arms == SpatialArms.LEFT | SpatialArms.DOWN:
        return [(x, half_y) for x in range(half_x + 1)] + [
            (half_x, y) for y in range(cube_shape.y, half_y, -1)
        ]


def _get_bottom_stabilizer_spatial_cube_qubits(
    cube_shape: PlaquetteShape2D,
) -> list[tuple[float, float]]:
    """The stabilizer measurements at the spatial cubes will be included in the
    logical observable.

    For simplicity of implementation, this function
    include all the measurement qubits of the spatial basis in the results and
    will filter out the qubits not used in the measurement records in
    ``inplace_add_observable``.
    """
    return [
        (i + 0.5, j + 0.5)
        for i in range(cube_shape.x)
        for j in range(cube_shape.y)
        if (i + j) % 2 == 0
    ]
