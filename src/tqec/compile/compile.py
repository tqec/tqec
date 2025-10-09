"""Defines :func:`~.compile.compile_block_graph`."""

from typing import Final, Literal

from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.convention import FIXED_BULK_CONVENTION, Convention
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.compile.specs.base import CubeSpec, PipeSpec
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import Cube
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.position import BlockPosition3D, Direction3D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

_DEFAULT_SCALABLE_QUBIT_SHAPE: Final = PhysicalQubitScalable2D(
    LinearFunction(4, 5), LinearFunction(4, 5)
)

_DEFAULT_BLOCK_REPETITIONS: LinearFunction = LinearFunction(2, -1)


def _get_template_from_layer(
    root: BaseLayer | BaseComposedLayer,
) -> RectangularTemplate:
    """Get a unique template from any given layer.

    This helper function try its best to recover the template a given layer uses.

    Raises:
        TQECError: if an instance of :class:`.BaseLayer` is something else than an instance of
            :class:`.PlaquetteLayer`, because :class:`.PlaquetteLayer` is the only class from which
            we can recover a template instance.
        TQECError: if an instance of :class:`.SequencedLayers` contains sub-layers with
            different templates.
        NotImplementedError: if an unknown layer is found.

    Returns:
        the template used by the provided ``root`` layer.

    """
    if isinstance(root, BaseLayer):
        if not isinstance(root, PlaquetteLayer):
            raise TQECError(
                f"Trying to get the Template from a {type(root).__name__} "
                "instance that does not have any Template."
            )
        return root.template
    elif isinstance(root, SequencedLayers):
        possible_templates = {_get_template_from_layer(layer) for layer in root.layer_sequence}
        if len(possible_templates) > 1:
            raise TQECError(
                "Multiple possible Template found:\n  -"
                + "\n  -".join(type(t).__name__ for t in possible_templates)
                + "\nWhich is not supported at the moment."
            )
        return next(iter(possible_templates))
    elif isinstance(root, RepeatedLayer):
        return _get_template_from_layer(root.internal_layer)
    else:
        raise NotImplementedError("Unknown layer type encountered:", type(root).__name__)


def compile_block_graph(
    block_graph: BlockGraph,
    convention: Convention = FIXED_BULK_CONVENTION,
    observables: list[CorrelationSurface] | Literal["auto"] | None = "auto",
    block_temporal_height: LinearFunction = _DEFAULT_BLOCK_REPETITIONS,
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
        block_temporal_height: the number of rounds of stabilizer measurements
            (ignoring one layer for initialization and another for final measurement).
            Defaults to `2k-1`.

    Returns:
        A :class:`TopologicalComputationGraph` object that can be used to generate a
        ``stim.Circuit`` and scale easily.

    """
    # All the ports should be filled before compiling the block graph.
    if block_graph.num_ports != 0:
        raise TQECError(
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

    # We need to know exactly which spatial pipes will be placed on a time slice where extended
    # plaquettes will be used, in order to adapt the schedule of the measurement layer.
    def has_pipes_in_both_spatial_dimensions(cube: Cube) -> bool:
        return frozenset(
            pipe.direction for pipe in block_graph.pipes_at(cube.position) if pipe.kind.is_spatial
        ) == frozenset([Direction3D.X, Direction3D.Y])

    extended_stabilizers_pipe_slices: frozenset[int] = frozenset(
        pipe.u.position.z
        for pipe in block_graph.pipes
        if (
            pipe.direction == Direction3D.Y
            and (
                has_pipes_in_both_spatial_dimensions(pipe.u)
                ^ has_pipes_in_both_spatial_dimensions(pipe.v)
            )
        )
    )
    cube_specs = {
        cube: CubeSpec.from_cube(cube, block_graph, extended_stabilizers_pipe_slices)
        for cube in block_graph.cubes
    }

    # 0. Get the abstract observables to be included in the compiled circuit.
    obs_included: list[AbstractObservable] = []
    if observables is not None:
        if observables == "auto":
            observables = block_graph.find_correlation_surfaces()
        include_temporal_hadamard_pipes = convention.name == "fixed_bulk"
        obs_included = [
            compile_correlation_surface_to_abstract_observable(
                block_graph, surface, include_temporal_hadamard_pipes
            )
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
        graph.add_cube(position, convention.triplet.cube_builder(spec, block_temporal_height))

    # 3. Add pipes to the graph
    # Note that the order of the pipes to add is important.
    # To keep the time-direction pipes from removing the extra resets
    # added by the space-direction pipes, we first add the time-direction pipes
    pipes = block_graph.pipes
    time_pipes = [pipe for pipe in pipes if pipe.direction == Direction3D.Z]
    temporal_hadamard_z_positions: set[int] = {
        pipe.u.position.z for pipe in time_pipes if pipe.kind.has_hadamard
    }
    space_pipes = [pipe for pipe in pipes if pipe.direction != Direction3D.Z]
    for pipe in time_pipes + space_pipes:
        pos1, pos2 = pipe.u.position, pipe.v.position
        pos1 = BlockPosition3D(pos1.x, pos1.y, pos1.z)
        pos2 = BlockPosition3D(pos2.x, pos2.y, pos2.z)
        template1 = _get_template_from_layer(graph.get_cube(pos1))
        template2 = _get_template_from_layer(graph.get_cube(pos2))
        key = PipeSpec(
            (cube_specs[pipe.u], cube_specs[pipe.v]),
            (template1, template2),
            pipe.kind,
            has_spatial_up_or_down_pipe_in_timeslice=(
                pos1.z == pos2.z and pos1.z in extended_stabilizers_pipe_slices
            ),
            at_temporal_hadamard_layer=(
                pipe.kind.is_temporal and pos1.z in temporal_hadamard_z_positions
            ),
        )
        graph.add_pipe(pos1, pos2, convention.triplet.pipe_builder(key, block_temporal_height))

    return graph
