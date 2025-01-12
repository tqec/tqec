"""Provides helper functions to add observables to circuits."""

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit
from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import JunctionArms
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe
from tqec.exceptions import TQECException
from tqec.position import (
    Direction3D,
    Displacement,
    Position3D,
    Shape2D,
    SignedDirection3D,
)
from tqec.scale import round_or_fail
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.templates.indices.layout import LayoutTemplate
from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXEdge, ZXKind, ZXNode


def inplace_add_observable(
    k: int,
    circuits: list[list[ScheduledCircuit]],
    template_slices: list[LayoutTemplate],
    abstract_observable: AbstractObservable,
    observable_index: int,
) -> None:
    """Inplace add the observable components to the circuits.

    The circuits are grouped by time slices and layers. The outer list
    represents the time slices and the inner list represents the layers.
    """
    top_data_qubits: dict[int, set[GridQubit]] = {}
    bottom_stabilizer_qubits: dict[int, set[GridQubit]] = {}

    def _block_shape(z: int, k: int) -> Shape2D:
        return template_slices[z].element_shape(k)

    # 1. The stabilizer measurements that will be added to the end of the first layer of circuits at z.
    for pipe in abstract_observable.bottom_stabilizer_pipes:
        for cube in pipe:
            # the stabilizer measurements included in spatial junctions will be
            # handled later
            if cube.is_spatial_junction:
                continue
            pos = cube.position
            qubits = _get_bottom_stabilizer_cube_qubits(
                _block_shape(pos.z, k),
                SignedDirection3D(pipe.direction, cube == pipe.u),
            )
            bottom_stabilizer_qubits.setdefault(pos.z, set()).update(
                _transform_coords_into_grid(template_slices, q, pos, k) for q in qubits
            )
    for junction, arms in abstract_observable.bottom_stabilizer_spatial_junctions:
        pos = junction.position
        qubits = _get_bottom_stabilizer_spatial_junction_qubits(
            _block_shape(pos.z, k), arms
        )
        bottom_stabilizer_qubits.setdefault(pos.z, set()).update(
            _transform_coords_into_grid(template_slices, q, pos, k) for q in qubits
        )

    # 2. The data qubit readouts that will be added to the end of the last layer of circuits at z.
    for pipe in abstract_observable.top_readout_pipes:
        u_pos = pipe.u.position
        qubits = _get_top_readout_pipe_qubits(_block_shape(u_pos.z, k), pipe.direction)
        top_data_qubits.setdefault(u_pos.z, set()).update(
            _transform_coords_into_grid(template_slices, q, u_pos, k) for q in qubits
        )
    for cube in abstract_observable.top_readout_cubes:
        pos = cube.position
        assert isinstance(cube.kind, ZXCube)
        qubits = _get_top_readout_cube_qubits(_block_shape(pos.z, k), cube.kind)
        top_data_qubits.setdefault(pos.z, set()).update(
            _transform_coords_into_grid(template_slices, q, pos, k) for q in qubits
        )
    for junction, arms in abstract_observable.top_readout_spatial_junctions:
        pos = junction.position
        qubits = _get_top_readout_spatial_junction_qubits(_block_shape(pos.z, k), arms)
        top_data_qubits.setdefault(pos.z, set()).update(
            _transform_coords_into_grid(template_slices, q, pos, k) for q in qubits
        )

    # Finally, convert the qubit sets to the measurement records at the specific circuit location
    # and add the observables to the circuits.
    for z, qubits in bottom_stabilizer_qubits.items():
        measurement_records = MeasurementRecordsMap.from_scheduled_circuit(
            circuits[z][0]
        )
        circuits[z][0].append_observable(
            observable_index,
            [stim.target_rec(measurement_records[q][-1]) for q in qubits],
        )

    for z, qubits in top_data_qubits.items():
        measurement_records = MeasurementRecordsMap.from_scheduled_circuit(
            circuits[z][-1]
        )
        circuits[z][-1].append_observable(
            observable_index,
            [stim.target_rec(measurement_records[q][-1]) for q in qubits],
        )


def _transform_coords_into_grid(
    template_slices: list[LayoutTemplate],
    local_coords: tuple[float, float],
    block_position: Position3D,
    k: int,
) -> GridQubit:
    """Transform local coordinates at a block to the global coordinates in the circuit.

    When calculating the coordinates of the measurement qubits, we use a local coordinate system
    in the individual blocks. The top-left corner of the block starts at (0, 0) and each column
    is separated by 0.5. That is, all the data qubits are placed at the integer coordinates while
    all the measurement qubits are placed at the half-integer coordinates.
    """
    template = template_slices[block_position.z]
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
    shape: Shape2D,
    cube_kind: ZXCube,
) -> list[tuple[float, float]]:
    obs_orientation = Direction3D(int(cube_kind.y == cube_kind.z))
    if obs_orientation == Direction3D.X:
        return [(x, shape.y // 2) for x in range(1, shape.x)]
    else:
        return [(shape.x // 2, y) for y in range(1, shape.y)]


def _get_top_readout_pipe_qubits(
    u_shape: Shape2D,
    connect_to: Direction3D,
) -> list[tuple[float, float]]:
    assert connect_to != Direction3D.Z
    if connect_to == Direction3D.X:
        return [(u_shape.x, u_shape.y // 2)]
    else:
        return [(u_shape.x // 2, u_shape.y)]


def _get_bottom_stabilizer_cube_qubits(
    cube_shape: Shape2D,
    connect_to: SignedDirection3D,
) -> list[tuple[float, float]]:
    stabilizers: list[tuple[float, float]] = []
    # We calculate the qubits for the connect_to=SignedDirection3D(Direction3D.X, True) case
    # and post-process(reflect, rotate) to get the correct orientation.
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


def _get_top_readout_spatial_junction_qubits(
    junction_shape: Shape2D,
    arms: JunctionArms,
) -> list[tuple[float, float]]:
    raise NotImplementedError()


def _get_bottom_stabilizer_spatial_junction_qubits(
    junction_shape: Shape2D,
    arms: JunctionArms,
) -> list[tuple[float, float]]:
    raise NotImplementedError()
