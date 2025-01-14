"""Describe the location of the observable measurements in the block graph."""

from dataclasses import dataclass

from tqec.compile.specs.enums import JunctionArms
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe
from tqec.position import Direction3D, Position3D
from tqec.computation.block_graph import BlockGraph
from tqec.computation.zx_graph import ZXEdge, ZXKind


@dataclass(frozen=True)
class AbstractObservable:
    """An abstract description of a logical observable in the
    :py:class:`~tqec.computation.BlockGraph`.

    A logical observable corresponds to all the
    `OBSERVABLE_INCLUDE <https://github.com/quantumlib/Stim/blob/main/doc/gates.md#OBSERVABLE_INCLUDE>`_
    instructions with the same observable index in the ``stim`` circuit
    and is composed of a set of measurements. Abstract observable
    specifies where are the measurements located in the block graph.

    Attributes:
        top_readout_cubes: A set of cubes of which a straight line of data
            qubit readouts on the top face should be included in the observable.
        top_readout_pipes: A set of pipes of which a single data qubit readout
            on the top face should be included in the observable. The data qubit
            is on the center of the interface between the two cubes. The other
            data qubit readouts that may be included in the observable will be
            handled by the ``top_readout_cubes`` set.
        bottom_stabilizer_pipes: A set of pipes of which a region of stabilizer
            measurements on the bottom face, which actually takes place in the
            cubes it connects, should be included in the observable.
        top_readout_spatial_junctions: A set of spatial junctions with the arm
            flags, of which the data qubit readouts on the top face should be
            included in the observable.
        bottom_stabilizer_spatial_junctions: A set of spatial junctions of which
            the stabilizer measurements on the bottom face should be included in
            the observable.
    """

    top_readout_cubes: frozenset[Cube] = frozenset()
    top_readout_pipes: frozenset[Pipe] = frozenset()
    bottom_stabilizer_pipes: frozenset[Pipe] = frozenset()
    top_readout_spatial_junctions: frozenset[tuple[Cube, JunctionArms]] = frozenset()
    bottom_stabilizer_spatial_junctions: frozenset[Cube] = frozenset()


def compile_correlation_surface_to_abstract_observable(
    block_graph: BlockGraph,
    correlation_surface: CorrelationSurface,
) -> AbstractObservable:
    """Compile a ``CorrelationSurface`` into an ``AbstractObservable`` in the
    block graph.

    The correlation surface translates into measurements to be included in the
    observable in two main ways:

    1. The surface attaches to the top face of some blocks. This means that part
    of the logical operator is measured by reading the data qubits. The parity
    change must be accounted for, and the measurement results should be included
    in the tracked logical observable.

    2. The surface spans the XY plane within some blocks. This represents a
    region of stabilizer measurements in the basis of the surface, whose products
    give the parity of the logical operators on the surface edges. Stabilizer
    measurements need to be included in the tracked logical observable to account
    for the correlation between logical operators at different spatial locations.
    We choose the stabilizer measurements at the first layer (i.e., the earliest
    in time or the bottom face of the block), since with sufficiently advanced
    software we will have greater confidence in these measurements earlier and
    in principle be able to make decisions based on these measurements earlier.

    The compilation process is as follows:

    1. Find all the spatial junctions involved in the correlation surface. For
    each junction:

    - If a surface is in the XY plane, include the stabilizer measurements at
    the bottom of the junction in the observable, and add the junction to the
    ``bottom_stabilizer_spatial_junctions`` set.

    - If a surface is perpendicular to the XY plane, include data qubit readouts
    on the top face of the junction in the observable. Correlation surfaces
    parallel to the junction's normal direction are guaranteed to attach to an
    even number of arms.
        - If exactly two arms touch the surface, add the junction and arms to the
        ``top_readout_spatial_junctions`` set.
        - If four arms touch the surface, split the arms into two pairs (e.g.
        ``JunctionArms.LEFT | JunctionArms.DOWN`` and
        ``JunctionArms.RIGHT | JunctionArms.UP``), and add the junction and arms
        to the ``top_readout_spatial_junctions`` set.

    2. Iterate over all the edges in the correlation surface. For each edge:
    - If the edge is vertical, check if the surface is attached to the top face
    of the top cube. If so, add the top cube to the ``top_readout_cubes`` set.
    - If the edge is horizontal, check if the surface is attached to the top face
    of the pipe. If so, add the pipe to the ``top_readout_pipes`` set; otherwise,
    add the pipe to the ``bottom_stabilizer_pipes`` set.
    - For each cube in the pipe, ignore the spatial junctions (already handled),
    and check if the surface is attached to the top face of the cube. If so, add
    the cube to the ``top_readout_cubes`` set.

    Warning:
        The corresponding ZX graph of the block graph must support the correlation
        surface. Otherwise, the behavior is undefined.

    Args:
        block_graph: The block graph whose corresponding ZX graph supports the
            correlation surface.
        correlation_surface: The correlation surface to convert into an abstract
            observable.

    Returns:
        The abstract observable corresponding to the correlation surface in the block graph.

    Raises:
        TQECException: If the block graph has open ports.
    """
    # 0. Handle single node edge case
    if correlation_surface.has_single_node:
        return AbstractObservable(top_readout_cubes=frozenset(block_graph.nodes))

    endpoints_to_edge: dict[frozenset[Position3D], list[ZXEdge]] = {}
    for edge in correlation_surface.span:
        endpoints = frozenset({edge.u.position, edge.v.position})
        endpoints_to_edge.setdefault(endpoints, []).append(edge)

    top_readout_cubes: set[Cube] = set()
    top_readout_pipes: set[Pipe] = set()
    bottom_stabilizer_pipes: set[Pipe] = set()
    top_readout_spatial_junctions: set[tuple[Cube, JunctionArms]] = set()
    bottom_stabilizer_spatial_junctions: set[Cube] = set()

    # 1. Handle all spatial junctions
    for node in correlation_surface.nodes:
        cube = block_graph[node.position]
        if not cube.is_spatial_junction:
            continue
        zx = cube.to_zx_node()
        zx_flipped = zx.with_zx_flipped()
        # correlation surface perpendicular to the normal direction of the junction
        # accounts for the bottom stabilizer measurements
        if zx.kind != node.kind:
            bottom_stabilizer_spatial_junctions.add(cube)
        # correlation surface parallel to the normal direction of the junction
        # accounts for the top readout measurements
        # we need to record the arm flags to specify different shapes of the
        # observable lines, e.g. L-shape, 7-shape, -- shape, etc.
        if zx_flipped.kind != node.kind:
            # check correlation edges in the junction arms
            arms = JunctionArms.NONE
            for arm, shift in JunctionArms.get_map_from_arm_to_shift().items():
                edges = endpoints_to_edge.get(
                    frozenset({cube.position, cube.position.shift_by(*shift)})
                )
                # The OR operation works because JunctionArms.NONE.value == 0
                if edges is not None and any(n == zx for edge in edges for n in edge):
                    arms |= arm
            assert len(arms) in {
                2,
                4,
            }, "The correlation parity should be even for parallel correlation surface."
            # Two separate lines in the junction
            # By convention, we always split the four arms into [LEFT | DOWN] and [RIGHT | UP]
            if len(arms) == 4:
                top_readout_spatial_junctions.add(
                    (cube, JunctionArms.LEFT | JunctionArms.DOWN)
                )
                top_readout_spatial_junctions.add(
                    (cube, JunctionArms.RIGHT | JunctionArms.UP)
                )
            else:
                top_readout_spatial_junctions.add((cube, arms))

    # 2. Handle all the pipes
    def has_obs_include(cube: Cube, correlation: ZXKind) -> bool:
        """Check if the top data qubit readout should be included in the
        observable.
        """
        if cube.is_y_cube:
            return True
        assert isinstance(cube.kind, ZXCube)
        # No pipe at the top
        if block_graph.has_edge_between(cube.position, cube.position.shift_by(0, 0, 1)):
            return False
        # The correlation surface must be attached to the top face
        return cube.kind.z.value == correlation.value

    for edge in correlation_surface.span:
        pipe = block_graph.get_edge(edge.u.position, edge.v.position)
        # Vertical pipes
        if pipe.direction == Direction3D.Z:
            if has_obs_include(pipe.v, edge.v.kind):
                top_readout_cubes.add(pipe.v)
            continue
        # Horizontal pipes
        pipe_top_face = pipe.kind.z
        assert pipe_top_face is not None, "The pipe is guaranteed to be spatial."
        # There is correlation surface attached to the top of the pipe
        if pipe_top_face.value == edge.u.kind.value:
            top_readout_pipes.add(pipe)
            for cube, node in zip(pipe, edge):
                # Spatial junctions have already been handled
                if cube.is_spatial_junction:
                    continue
                if has_obs_include(cube, node.kind):
                    top_readout_cubes.add(cube)
        elif not all(cube.is_spatial_junction for cube in pipe):
            bottom_stabilizer_pipes.add(pipe)

    return AbstractObservable(
        frozenset(top_readout_cubes),
        frozenset(top_readout_pipes),
        frozenset(bottom_stabilizer_pipes),
        frozenset(top_readout_spatial_junctions),
        frozenset(bottom_stabilizer_spatial_junctions),
    )
