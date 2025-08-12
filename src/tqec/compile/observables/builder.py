"""Provides helper functions to add observables to circuits."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    CubeWithArms,
    PipeWithArms,
    PipeWithObservableBasis,
)
from tqec.templates.layout import LayoutTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.position import PlaquetteShape2D, Position3D
from tqec.utils.scale import round_or_fail


@dataclass(frozen=True)
class Observable:
    """Logical observable consisting of a list of measurements.

    Attributes:
        observable_index: The index of the observable in the circuit.
        measured_qubits: The qubits whose measurements will be included in the
            observable.
        measurement_offsets: The offsets of the measurements in the circuit.
            This should have the same length as `measured_qubits` and
            contain strictly negative values.

    """

    observable_index: int
    measured_qubits: list[GridQubit]
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if len(self.measured_qubits) != len(self.measurement_offsets):
            raise TQECError(
                "The number of measured qubits and measurement offsets must be the same."
            )
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECError("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        """Return the ``stim`` instruction reprensented by ``self``."""
        return stim.CircuitInstruction(
            "OBSERVABLE_INCLUDE",
            [stim.target_rec(offset) for offset in sorted(self.measurement_offsets)],
            [self.observable_index],
        )


class ObservableComponent(Enum):
    BOTTOM_STABILIZERS = "bottom_stabilizers"
    TOP_READOUTS = "top_readouts"
    REALIGNMENT = "realignment"


Coordinates2D = tuple[float, float] | tuple[int, int]


class CubeObservableQubitsBuilder(Protocol):
    """Build the qubits whose measurements will be included in the logical observable that is
    supported by the cube.

    This calculates the coordinates of these data qubits in the local coordinate system.

    """

    def __call__(self, shape: PlaquetteShape2D, cube: CubeWithArms) -> Sequence[Coordinates2D]:
        """Build the qubit coordinates whose measurement will be included in the observable."""
        ...


class PipeObservableQubitsBuilder(Protocol):
    """Build the qubits whose measurements will be included in the logical observable that is
    supported by the pipe.

    This calculates the coordinates of that data qubit in the local coordinate system of the cube at
    the head of the pipe.

    """

    def __call__(self, shape: PlaquetteShape2D, pipe: PipeWithArms) -> Sequence[Coordinates2D]:
        """Build the qubit coordinates whose measurement will be included in the observable."""
        ...


class TemporalPipeObservableQubitsBuilder(Protocol):
    """Build the qubits whose measurements will be included in the logical observable that is
    supported by the temporal pipe.

    This calculates the coordinates of that data qubit in the local coordinate system of the cube at
    the head of the pipe.

    """

    def __call__(
        self, shape: PlaquetteShape2D, pipe: PipeWithObservableBasis
    ) -> Sequence[Coordinates2D]:
        """Build the qubit coordinates whose measurement will be included in the observable."""
        ...


@dataclass
class ObservableBuilder:
    """Compute the qubits whose measurements will be included in the logical observable.

    The builders can include the qubits that are not in the circuit like qubits in the
    scretched stabilizers to simplify the calculation. The qubits that are not
    measured in the circuit will be ignored when calling
    ``get_observable_with_measurement_records``.

    """

    cube_top_readouts_builder: CubeObservableQubitsBuilder
    pipe_top_readouts_builder: PipeObservableQubitsBuilder
    cube_bottom_stabilizers_builder: CubeObservableQubitsBuilder
    pipe_bottom_stabilizers_builder: PipeObservableQubitsBuilder
    pipe_temporal_hadamard_builder: TemporalPipeObservableQubitsBuilder

    def build(
        self,
        k: int,
        template: LayoutTemplate,
        observable: AbstractObservable,
        component: ObservableComponent,
    ) -> set[GridQubit]:
        """Compute the qubits whose measurements will be included in the observable.

        Args:
            k: The scaling parameter.
            template: The layout template of the circuit.
            observable: The abstract observable that builds the observable qubits from.
            component: The component of the observable to compute.

        Returns:
            A set of qubits whose measurements will be included in the logical observable.
            The qubits are in the global coordinate system of the circuit.

        """
        shape = template.element_shape(k)
        obs_qubits: set[GridQubit] = set()

        # The stabilizer measurements that will be added to the end of the
        # first layer of circuits at z.
        if component == ObservableComponent.BOTTOM_STABILIZERS:
            for cube in observable.bottom_stabilizer_cubes:
                obs_qubits.update(
                    self.transform_coords_into_grid(
                        k,
                        template,
                        self.cube_bottom_stabilizers_builder(shape, cube),
                        cube.cube.position,
                    )
                )
            for pipe in observable.bottom_stabilizer_pipes:
                obs_qubits.update(
                    self.transform_coords_into_grid(
                        k,
                        template,
                        self.pipe_bottom_stabilizers_builder(shape, pipe),
                        pipe.pipe.u.position,
                    )
                )
        # The readouts that will be added to the end of the last layer of circuits at z.
        elif component == ObservableComponent.TOP_READOUTS:
            for cube in observable.top_readout_cubes:
                obs_qubits.update(
                    self.transform_coords_into_grid(
                        k,
                        template,
                        self.cube_top_readouts_builder(shape, cube),
                        cube.cube.position,
                    )
                )
            for pipe in observable.top_readout_pipes:
                obs_qubits.update(
                    self.transform_coords_into_grid(
                        k,
                        template,
                        self.pipe_top_readouts_builder(shape, pipe),
                        pipe.pipe.u.position,
                    )
                )
        else:  # component == ObservableComponent.REALIGNMENT
            for hadamard_pipe in observable.temporal_hadamard_pipes:
                obs_qubits.update(
                    self.transform_coords_into_grid(
                        k,
                        template,
                        self.pipe_temporal_hadamard_builder(shape, hadamard_pipe),
                        hadamard_pipe.pipe.u.position,
                    )
                )
        return obs_qubits

    @staticmethod
    def transform_coords_into_grid(
        k: int,
        template: LayoutTemplate,
        local_coords: Iterable[tuple[float, float] | tuple[int, int]],
        block_position: Position3D,
    ) -> set[GridQubit]:
        """Transform local coordinates at a block to the global coordinates in the circuit.

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
        transformed_coords: set[GridQubit] = set()
        for coords in local_coords:
            x = block_position.x * width + round_or_fail((coords[0] - 0.5) * template_increments.x)
            y = block_position.y * height + round_or_fail((coords[1] - 0.5) * template_increments.y)
            transformed_coords.add(GridQubit(x, y))
        return transformed_coords


def get_observable_with_measurement_records(
    qubits: set[GridQubit],
    measurement_records: MeasurementRecordsMap,
    observable_index: int,
    ignore_qubits_with_no_measurement: bool = True,
) -> Observable:
    """Calculate the measurement offsets of the observable qubits measured at the end of the circuit
    and construct the observable.

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
        raise TQECError(
            "Some qubits are not measured in the circuit. Set "
            "ignore_qubits_with_no_measurement to True to ignore them."
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
