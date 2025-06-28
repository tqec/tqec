"""Provides helper functions to add observables to circuits."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import Pipe
from tqec.templates.layout import LayoutTemplate
from tqec.utils.enums import Basis, Orientation
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
    measured_qubits: list[GridQubit]
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if len(self.measured_qubits) != len(self.measurement_offsets):
            raise TQECException(
                "The number of measured qubits and measurement offsets must be the same."
            )
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "OBSERVABLE_INCLUDE",
            [stim.target_rec(offset) for offset in sorted(self.measurement_offsets)],
            [self.observable_index],
        )


class CubeTopReadoutsBuilder(Protocol):
    """The data qubits on the middle line of the cube will be read out and
    included in the logical observable.

    This calculates the coordinates of these data qubits in the local coordinate
    system.
    """

    def __call__(
        self, shape: PlaquetteShape2D, obs_orientation: Orientation, /
    ) -> list[tuple[int, int]]: ...


class SpatialCubeTopReadoutsBuilder(Protocol):
    """The data qubits at the spatial cubes will be read out and included in
    the logical observable.

    This function calculates the coordinates of the data qubits in the
    local coordinate system of the cube based on which arms the
    correlation surface touches.
    """

    def __call__(
        self, shape: PlaquetteShape2D, arms: SpatialArms, observable_basis: Basis, /
    ) -> list[tuple[int, int]]: ...


class PipeTopReadoutsBuilder(Protocol):
    """The top line at a pipe is actually a single data qubits at the interface
    of the two connected cubes.

    The measurement result of this qubit will be included in the logical
    observable. This calculates the coordinates of that data qubit in the local
    coordinate system of the cube at the head of the pipe.
    """

    def __call__(self, shape: PlaquetteShape2D, pipe: Pipe, /) -> list[tuple[int, int]]: ...


class CubeBottomStabilizersBuilder(Protocol):
    """The stabilizer measurements at the bottom of the cube will be included
    in the logical observable. Note that only half of the stabilizers in the
    basis of the boundary that the cube connects to will be included. Each cube
    is only responsible for the stabilizer measurements within its bounding
    box. Collecting the measurements from the two cubes connected by the pipe
    will give the full stabilizer measurements, of which the product determines
    the parity of the logical operators.

    This calculates the coordinates of the measurement qubits in the local
    coordinate system of the cube.
    """

    def __call__(
        self,
        shape: PlaquetteShape2D,
        connect_to: SignedDirection3D,
        stabilizer_basis: Basis,
        /,
    ) -> list[tuple[float, float]]: ...


class SpatialCubeBottomStabilizersBuilder(Protocol):
    """The stabilizer measurements at the spatial cubes will be included in the
    logical observable.
    """

    def __call__(
        self, shape: PlaquetteShape2D, stabilizer_basis: Basis, /
    ) -> list[tuple[float, float]]: ...


class TemporalHadamardIncludesBuilder(Protocol):
    """Measurements at the temporal logical Hadamard layer that might be included
    in the logical Z observable.
    """

    def __call__(
        self,
        shape: PlaquetteShape2D,
        observable_basis: Basis,
        z_orientation: Orientation,
        /,
    ) -> list[tuple[float, float]]: ...


@dataclass
class ObservableBuilder:
    """Compute the qubits whose measurements will be included in the logical
    observable.

    The builders can include the qubits that are not in the circuit like qubits in the
    scretched stabilizers to simplify the calculation. The qubits that are not
    measured in the circuit will be ignored when calling ``get_observable_with_measurement_records``.
    """

    cube_top_readouts_builder: CubeTopReadoutsBuilder
    spatial_cube_top_readouts_builder: SpatialCubeTopReadoutsBuilder
    pipe_top_readouts_builder: PipeTopReadoutsBuilder
    cube_bottom_stabilizers_builder: CubeBottomStabilizersBuilder
    spatial_cube_bottom_stabilizers_builder: SpatialCubeBottomStabilizersBuilder
    temporal_hadamard_includes_builder: TemporalHadamardIncludesBuilder = lambda *args: []


def _transform_coords_into_grid(
    template: LayoutTemplate,
    local_coords: tuple[float, float] | tuple[int, int],
    block_position: Position3D,
    k: int,
) -> GridQubit:
    """Transform local coordinates at a block to the global coordinates in the
    circuit.

    When calculating the coordinates of the measurement qubits, we use a local
    coordinate system in the individual blocks. The top-left corner of the
    block starts at (0, 0) and each column is separated by 0.5. That is, all
    the data qubits are placed at the integer coordinates while all the
    measurement qubits are placed at the half-integer coordinates.

    This convention helps reducing the number of arguments needed to pass around
    and simplifies the calculation of the qubit coordinates. The global coordinates
    are calculated by offsetting the local coordinates by the global position of
    the block and accounting for the ``Template.default_increments``.
    """
    block_shape = template.element_shape(k)
    template_increments = template.get_increments()
    width = block_shape.x * template_increments.x
    height = block_shape.y * template_increments.y
    x = block_position.x * width + round_or_fail((local_coords[0] - 0.5) * template_increments.x)
    y = block_position.y * height + round_or_fail((local_coords[1] - 0.5) * template_increments.y)
    return GridQubit(x, y)


class ObservableComponent(Enum):
    BOTTOM_STABILIZERS = "bottom_stabilizers"
    TOP_READOUTS = "top_readouts"
    REALIGNMENT = "realignment"


def compute_observable_qubits(
    k: int,
    obs_slice: AbstractObservable,
    template: LayoutTemplate,
    obs_builder: ObservableBuilder,
    component: ObservableComponent,
) -> set[GridQubit]:
    """Compute the qubits whose measurements will be included in the observable.

    This function targets at a single time slice (circuit layer) and calculates
    the qubits that will be included in the logical observable at that time.

    Args:
        k: The scaling parameter.
        obs_slice: The slice of an abstract observable at the time step.
        template: The layout template of the block at the time step.
        at_bottom: Whether the observable is at the bottom of the block.

    """
    shape = template.element_shape(k)
    obs_qubits: set[GridQubit] = set()

    def collect(
        pos: Position3D,
        qubits: Iterable[tuple[float, float] | tuple[int, int]],
    ) -> None:
        obs_qubits.update(_transform_coords_into_grid(template, q, pos, k) for q in qubits)

    # The stabilizer measurements that will be added to the end of the first layer of circuits at z.
    if component == ObservableComponent.BOTTOM_STABILIZERS:
        for pipe in obs_slice.bottom_stabilizer_pipes:
            for cube in pipe:
                # the stabilizer measurements included in spatial cubes will be
                # handled later
                if cube.is_spatial:
                    continue
                assert isinstance(cube.kind, ZXCube)
                stabilizer_basis = cube.kind.get_basis_along(Direction3D(1 - pipe.direction.value))
                collect(
                    cube.position,
                    obs_builder.cube_bottom_stabilizers_builder(
                        shape,
                        SignedDirection3D(pipe.direction, cube == pipe.u),
                        stabilizer_basis,
                    ),
                )
        for cube in obs_slice.bottom_stabilizer_spatial_cubes:
            assert isinstance(cube.kind, ZXCube)
            collect(
                cube.position,
                obs_builder.spatial_cube_bottom_stabilizers_builder(shape, cube.kind.x),
            )
        return obs_qubits

    if component == ObservableComponent.TOP_READOUTS:
        # The readouts that will be added to the end of the last layer of circuits at z.
        for pipe in obs_slice.top_readout_pipes:
            collect(
                pipe.u.position,
                obs_builder.pipe_top_readouts_builder(shape, pipe),
            )
        for cube in obs_slice.top_readout_cubes:
            assert isinstance(cube.kind, ZXCube)
            # Determine the middle line orientation based on the cube kind.
            # Since the basis of the top face decides the measurement basis of the data
            # qubits, i.e. the logical operator basis. We only need to find the spatial
            # boundaries that the logical operator can be attached to.
            obs_orientation = (
                Orientation.VERTICAL if cube.kind.y == cube.kind.z else Orientation.HORIZONTAL
            )
            collect(
                cube.position,
                obs_builder.cube_top_readouts_builder(shape, obs_orientation),
            )
        for cube, arms in obs_slice.top_readout_spatial_cubes:
            assert isinstance(cube.kind, ZXCube)
            collect(
                cube.position,
                obs_builder.spatial_cube_top_readouts_builder(shape, arms, cube.kind.z),
            )
        return obs_qubits

    else:  # component == ObservableComponent.REALIGNMENT
        for pipe, obs_basis in obs_slice.temporal_hadamard_pipes:
            z_orientation = (
                Orientation.VERTICAL
                if pipe.kind.get_basis_along(Direction3D.Y) == Basis.Z
                else Orientation.HORIZONTAL
            )
            collect(
                pipe.u.position,
                obs_builder.temporal_hadamard_includes_builder(shape, obs_basis, z_orientation),
            )
        return obs_qubits


def get_observable_with_measurement_records(
    qubits: set[GridQubit],
    measurement_records: MeasurementRecordsMap,
    observable_index: int,
    ignore_qubits_with_no_measurement: bool = True,
) -> Observable:
    """Calculate the measurement offsets of the observable qubits measured at
    the end of the circuit and construct the observable.

    Args:
        qubits: The qubits whose measurements will be included in the observable.
        measurement_records: The measurement records of the qubits in a circuit.
        observable_index: The index of the observable.
        ignore_qubits_with_no_measurement: Whether to skip qubits that are not
            measured in the circuit. If set to False, an exception will be raised
            if any of the qubits is not measured.

    Returns:
        The logical observable.

    """
    if not ignore_qubits_with_no_measurement and any(
        len(measurement_records.mapping.get(q, [])) == 0 for q in qubits
    ):
        raise TQECException(
            "Some qubits are not measured in the circuit. Set ignore_qubits_with_no_measurement to True to ignore them."
        )

    measured_qubits = [
        q
        for q in qubits
        # Ignore those qubits that are not measured in the circuit.
        # This is required because the some observable builders
        # include the qubits that are not in the circuit like qubits
        # in the scretched stabilizers to simplify the calculation.
        if q in measurement_records
    ]
    measurement_offsets = [measurement_records[q][-1] for q in measured_qubits]
    return Observable(observable_index, measured_qubits, measurement_offsets)
