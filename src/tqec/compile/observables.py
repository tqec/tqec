"""Provides helper functions to add observables to circuits."""

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit
from tqec.computation.abstract_observable import AbstractObservable
from tqec.computation.block_graph import Cube, Pipe
from tqec.computation.cube import ZXCube
from tqec.exceptions import TQECException
from tqec.position import Direction3D, Displacement, Shape2D
from tqec.scale import round_or_fail
from tqec.templates.layout import LayoutTemplate


def get_center_qubit_at_horizontal_pipe(
    pipe: Pipe, block_shape: Shape2D, template_increments: Displacement
) -> GridQubit:
    """Get the single center qubit of a horizontal pipe."""
    if pipe.direction == Direction3D.Z:
        raise TQECException("Can only get center qubit for horizontal pipes.")

    width = block_shape.x * template_increments.x
    height = block_shape.y * template_increments.y
    half_increment_x = template_increments.x // 2
    half_increment_y = template_increments.y // 2
    u_pos = pipe.u.position
    if pipe.direction == Direction3D.X:
        return GridQubit(
            (1 + u_pos.x) * width - half_increment_x,
            round_or_fail((0.5 + u_pos.y) * height) - half_increment_y,
        )
    else:
        return GridQubit(
            round_or_fail((0.5 + u_pos.x) * width) - 1, (1 + u_pos.y) * height - 1
        )


def get_midline_qubits_for_cube(
    cube: Cube, block_shape: Shape2D, template_increments: Displacement
) -> list[GridQubit]:
    """Get the midline qubits for a cube."""
    if cube.is_spatial_junction or cube.is_port:
        raise TQECException(
            "Cannot get midline qubits for a spatial junction cube or a port."
        )
    kind = cube.kind
    assert isinstance(kind, ZXCube)
    midline_orientation = Direction3D(int(kind.y == kind.z))

    width = block_shape.x * template_increments.x
    height = block_shape.y * template_increments.y
    half_increment_x = template_increments.x // 2
    half_increment_y = template_increments.y // 2
    pos = cube.position
    if midline_orientation == Direction3D.X:
        return [
            GridQubit(col, round_or_fail((0.5 + pos.y) * height) - half_increment_y)
            for col in range(
                pos.x * width + half_increment_x,
                (pos.x + 1) * width - half_increment_x,
                template_increments.x,
            )
        ]
    else:
        return [
            GridQubit(round_or_fail((0.5 + pos.x) * width) - half_increment_x, row)
            for row in range(
                pos.y * height + half_increment_y,
                (pos.y + 1) * height - half_increment_y,
                template_increments.y,
            )
        ]


def get_stabilizer_region_qubits_for_pipe(
    pipe: Pipe,
    block_shape: Shape2D,
    template_increments: Displacement,
) -> list[GridQubit]:
    stabilizer_qubits: list[GridQubit] = []
    if pipe.direction == Direction3D.Z:
        raise TQECException(
            "Can only get stabilizer region qubits for horizontal pipes."
        )

    width = block_shape.x * template_increments.x
    height = block_shape.y * template_increments.y
    half_increment_x = template_increments.x // 2
    half_increment_y = template_increments.y // 2
    u_pos = pipe.u.position
    if pipe.direction == Direction3D.X:
        block_border_x = (u_pos.x + 1) * width - half_increment_x
        for i in range(block_shape.x // 2):
            x1 = block_border_x - template_increments.x * i - half_increment_x
            x2 = block_border_x + template_increments.x * i + half_increment_x
            for j in range(block_shape.y // 2):
                y1 = (
                    template_increments.y * (1 - i % 2)
                    + 2 * template_increments.y * j
                    + u_pos.y * height
                )
                y2 = (
                    template_increments.y * (i % 2)
                    + 2 * template_increments.y * j
                    + u_pos.y * height
                )
                stabilizer_qubits.append(GridQubit(x1, y1))
                stabilizer_qubits.append(GridQubit(x2, y2))
    else:
        block_border_y = (u_pos.y + 1) * height - 1
        for j in range(block_shape.y // 2):
            y1 = block_border_y - template_increments.y * j - half_increment_y
            y2 = block_border_y + template_increments.y * j + half_increment_y
            for i in range(block_shape.x // 2):
                x1 = (
                    template_increments.x * (j % 2)
                    + 2 * template_increments.x * i
                    + u_pos.x * width
                )
                x2 = (
                    template_increments.x * (1 - j % 2)
                    + 2 * template_increments.x * i
                    + u_pos.x * width
                )
                stabilizer_qubits.append(GridQubit(x1, y1))
                stabilizer_qubits.append(GridQubit(x2, y2))
    return stabilizer_qubits


def inplace_add_observables(
    circuits: list[list[ScheduledCircuit]],
    template_slices: list[LayoutTemplate],
    abstract_observables: list[AbstractObservable],
    k: int,
) -> None:
    """Inplace add the observable components to the circuits.

    The circuits are grouped by time slices and layers. The outer list
    represents the time slices and the inner list represents the layers.
    """
    for i, observable in enumerate(abstract_observables):
        # Add the stabilizer region measurements to the end of the first layer of circuits at z.
        for pipe in observable.bottom_regions:
            z = pipe.u.position.z
            template = template_slices[z]
            stabilizer_qubits = get_stabilizer_region_qubits_for_pipe(
                pipe, template.element_shape(k), template.get_increments()
            )
            measurement_records = MeasurementRecordsMap.from_scheduled_circuit(
                circuits[z][0]
            )
            circuits[z][0].append_observable(
                i,
                [
                    stim.target_rec(measurement_records[q][-1])
                    for q in stabilizer_qubits
                ],
            )

        # Add the line measurements to the end of the last layer of circuits at z.
        for cube_or_pipe in observable.top_lines:
            if isinstance(cube_or_pipe, Cube):
                z = cube_or_pipe.position.z
                template = template_slices[z]
                qubits = get_midline_qubits_for_cube(
                    cube_or_pipe, template.element_shape(k), template.get_increments()
                )
            else:
                z = cube_or_pipe.u.position.z
                template = template_slices[z]
                qubits = [
                    get_center_qubit_at_horizontal_pipe(
                        cube_or_pipe,
                        template.element_shape(k),
                        template.get_increments(),
                    )
                ]
            measurement_records = MeasurementRecordsMap.from_scheduled_circuit(
                circuits[z][-1]
            )
            circuits[z][-1].append_observable(
                i,
                [stim.target_rec(measurement_records[q][-1]) for q in qubits],
            )
