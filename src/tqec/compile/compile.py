"""Defines :func:`~.compile.compile_block_graph`."""

from typing import Final, Literal

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.convention import FIXED_BULK_CONVENTION, Convention
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.compile.observables.builder import (
    compute_observable_qubits,
    get_observable_with_measurement_records,
)
from tqec.compile.specs.base import CubeSpec, PipeSpec
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.templates.layout import LayoutTemplate
from tqec.templates.qubit import QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition3D, Direction3D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

_DEFAULT_SCALABLE_QUBIT_SHAPE: Final = PhysicalQubitScalable2D(
    LinearFunction(4, 5), LinearFunction(4, 5)
)


def compile_block_graph(
    block_graph: BlockGraph,
    convention: Convention = FIXED_BULK_CONVENTION,
    observables: list[CorrelationSurface] | Literal["auto"] | None = "auto",
) -> TopologicalComputationGraph:
    """Compile a block graph.

    Args:
        block_graph: The block graph to compile.
        convention: convention used to generate the quantum circuits.
        observables: correlation surfaces that should be compiled into
            observables and included in the compiled circuit.
            If set to ``"auto"``, the correlation surfaces will be automatically
            determined from the block graph. If a list of correlation surfaces
            is provided, only those surfaces will be compiled into observables
            and included in the compiled circuit. If set to ``None``, no
            observables will be included in the compiled circuit.

    Returns:
        A :class:`TopologicalComputationGraph` object that can be used to generate a
        ``stim.Circuit`` and scale easily.
    """
    # All the ports should be filled before compiling the block graph.
    if block_graph.num_ports != 0:
        raise TQECException(
            "Can not compile a block graph with open ports into circuits. "
            "You might want to call `fill_ports` or `fill_ports_for_minimal_simulation` "
            "on the block graph before compiling it."
        )
    # Validate the graph can represent a valid computation.
    block_graph.validate()

    # Fix the shadowed faces of the cubes to avoid using spatial cubes
    # when a non-spatial cube can be used at the same position.
    # For example, when three XXZ cubes are connected in a row along the x-axis,
    # the middle one can be replaced by a ZXX cube because the faces along the
    # x-axis are shadowed by the connected pipes.
    block_graph = block_graph.fix_shadowed_faces()

    # Set the minimum z of block graph to 0.(time starts from zero)
    minz = min(cube.position.z for cube in block_graph.cubes)
    if minz != 0:
        block_graph = block_graph.shift_by(dz=-minz)

    cube_specs = {
        cube: CubeSpec.from_cube(cube, block_graph) for cube in block_graph.cubes
    }

    # 0. Get the abstract observables to be included in the compiled circuit.
    obs_included: list[AbstractObservable] = []
    if observables is not None:
        if observables == "auto":
            observables = block_graph.find_correlation_surfaces()
        obs_included = [
            compile_correlation_surface_to_abstract_observable(block_graph, surface)
            for surface in observables
        ]

    # 1. Create topological computation graph
    graph = TopologicalComputationGraph(
        _DEFAULT_SCALABLE_QUBIT_SHAPE,
        observables=obs_included,
        observable_builder=convention.triplet.observable_builder,
    )

    # 2. Add cubes to the graph
    for cube in block_graph.cubes:
        spec = cube_specs[cube]
        position = BlockPosition3D(cube.position.x, cube.position.y, cube.position.z)
        graph.add_cube(position, convention.triplet.cube_builder(spec))

    # 3. Add pipes to the graph
    # Note that the order of the pipes to add is important.
    # To keep the time-direction pipes from removing the extra resets
    # added by the space-direction pipes, we first add the time-direction pipes
    pipes = block_graph.pipes
    time_pipes = [pipe for pipe in pipes if pipe.direction == Direction3D.Z]
    space_pipes = [pipe for pipe in pipes if pipe.direction != Direction3D.Z]
    for pipe in time_pipes + space_pipes:
        pos1, pos2 = pipe.u.position, pipe.v.position
        pos1 = BlockPosition3D(pos1.x, pos1.y, pos1.z)
        pos2 = BlockPosition3D(pos2.x, pos2.y, pos2.z)
        key = PipeSpec(
            (cube_specs[pipe.u], cube_specs[pipe.v]),
            (QubitTemplate(), QubitTemplate()),
            pipe.kind,
        )
        graph.add_pipe(pos1, pos2, convention.triplet.pipe_builder(key))

    return graph


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
    from tqec.compile.observables.fixed_parity_builder import (
        FIXED_PARITY_OBSERVABLE_BUILDER,
    )

    for z in range(len(circuits)):
        obs_slice = abstract_observable.slice_at_z(z)
        for at_bottom in [True, False]:
            obs_qubits = compute_observable_qubits(
                k,
                obs_slice,
                template_slices[z],
                at_bottom,
                FIXED_PARITY_OBSERVABLE_BUILDER,
            )
            if not obs_qubits:
                continue
            circuit = circuits[z][0] if at_bottom else circuits[z][-1]
            measurement_records = MeasurementRecordsMap.from_scheduled_circuit(circuit)
            obs = get_observable_with_measurement_records(
                obs_qubits, measurement_records, observable_index
            )
            obs_instruction = obs.to_instruction()
            circuit.append_annotation(obs_instruction)
