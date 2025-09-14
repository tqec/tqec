"""Describe the location of the observable measurements in the block graph."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface, ZXEdge
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D

if TYPE_CHECKING:
    from pyzx.graph.graph_s import GraphS


@dataclass(frozen=True)
class CubeWithArms:
    """A cube with its arms in the block graph.

    The arms are used to specify the connectivity of a spatial cube in the graph
    or in a correlation surface. A regular cube should always have `arms` set to
    `SpatialArms.NONE`.

    Attributes:
        cube: The cube in the block graph.
        arms: The arms of the cube in the block graph or correlation surface.
            If the cube is not spatial, the arms should be set to
            `SpatialArms.NONE`.

    """

    cube: Cube
    arms: SpatialArms = SpatialArms.NONE

    def __post_init__(self) -> None:
        if self.arms != SpatialArms.NONE and not self.cube.is_spatial:
            raise TQECError(
                "The `arms` attribute should be `SpatialArms.NONE` for non-spatial cubes."
            )


@dataclass(frozen=True)
class PipeWithArms:
    """A pipe with the arms of the two cubes it connects in the block graph.

    Attributes:
        pipe: The pipe in the block graph.
        cube_arms: A tuple of arms of the two cubes (``u`` and ``v``) the pipe
            connects. If the cubes are not spatial, the arms should be set to
            `SpatialArms.NONE`.

    """

    pipe: Pipe
    cube_arms: tuple[SpatialArms, SpatialArms] = (SpatialArms.NONE, SpatialArms.NONE)


@dataclass(frozen=True)
class PipeWithObservableBasis:
    """A temporal Hadamard pipe with the attached observable basis at its head.

    Attributes:
        pipe: The temporal Hadamard pipe in the block graph.
        observable_basis: The basis of the correlation surface at the head of
            the pipe.

    """

    pipe: Pipe
    observable_basis: Basis

    def __post_init__(self) -> None:
        if not self.pipe.kind.has_hadamard or self.pipe.direction != Direction3D.Z:
            raise TQECError("The ``pipe`` should be a temporal Hadamard pipe.")


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
        top_readout_cubes: A set of cubes of which a line of data qubit readouts
            on the top face should be included in the observable.
        top_readout_pipes: A set of pipes of which a single data qubit readout
            on the top face might be included in the observable. The data qubit
            is on the center of the interface between the two cubes. The other
            data qubit readouts that may be included in the observable will be
            handled by the ``top_readout_cubes`` set.
        bottom_stabilizer_cubes: A set of spatial cubes of which the stabilizer
            measurements on the bottom face should be included in the observable.
            Usually, this is only used for the single-cube stability experiment
            where no pipes are involved. In other cases, the stabilizer measured
            at the bottom face of the cubes will be handled by the pipes
            connecting them, i.e., the ``bottom_stabilizer_pipes`` set.
        bottom_stabilizer_pipes: A set of pipes of which a region of stabilizer
            measurements on the bottom face, which actually takes place in the
            cubes it connects, should be included in the observable.
        temporal_hadamard_pipes: A set of temporal Hadamard pipes of which a
            single stabilizer measurements at the realignment layer represented
            by the pipe might be included in the logical observable. It is only
            relevant for the fixed-bulk convention, where the temporal Hadamard
            includes a realignment layer of stabilizers.

    """

    top_readout_cubes: frozenset[CubeWithArms] = frozenset()
    top_readout_pipes: frozenset[PipeWithArms] = frozenset()
    bottom_stabilizer_cubes: frozenset[CubeWithArms] = frozenset()
    bottom_stabilizer_pipes: frozenset[PipeWithArms] = frozenset()
    temporal_hadamard_pipes: frozenset[PipeWithObservableBasis] = frozenset()

    def slice_at_z(self, z: int) -> AbstractObservable:
        """Get the observable slice at the given z position."""
        return AbstractObservable(
            frozenset(c for c in self.top_readout_cubes if c.cube.position.z == z),
            frozenset(p for p in self.top_readout_pipes if p.pipe.u.position.z == z),
            frozenset(c for c in self.bottom_stabilizer_cubes if c.cube.position.z == z),
            frozenset(p for p in self.bottom_stabilizer_pipes if p.pipe.u.position.z == z),
            frozenset(p for p in self.temporal_hadamard_pipes if p.pipe.u.position.z == z),
        )


def compile_correlation_surface_to_abstract_observable(
    block_graph: BlockGraph,
    correlation_surface: CorrelationSurface,
    include_temporal_hadamard_pipes: bool = False,
) -> AbstractObservable:
    """Compile a ``CorrelationSurface`` into an ``AbstractObservable`` in the block graph.

    The correlation surface translates into measurements to be included in the
    observable in the following ways:

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

    3. A temporal Hadamard pipe under fixed-bulk convention includes a layer of
    realignment stabilizers, which might includes a single stabilizer measurements
    that need to be added to the observable.

    The compilation process is as follows:

    1. Find all the spatial cubes involved in the correlation surface. For
    each cube:

    - If a surface is perpendicular to the XY plane, include data qubit readouts
    on the top face of the cube in the observable. Correlation surfaces
    parallel to the cube's normal direction are guaranteed to attach to an
    even number of arms.
        - If exactly two arms touch the surface, add the cube and arms to the
        ``top_readout_cubes`` set.
        - If four arms touch the surface, split the arms into two pairs (e.g.
        ``SpatialArms.LEFT | SpatialArms.DOWN`` and
        ``SpatialArms.RIGHT | SpatialArms.UP``), and add the cube and arms
        to the ``top_readout_cubes`` set.

    2. Iterate over all the edges in the correlation surface. For each edge:
    - If the edge is vertical, check if the surface is attached to the top face
    of the top cube. If so, add the top cube to the ``top_readout_cubes`` set.
    If the edge is a hadamard edge, add the pipe to the ``temporal_hadamard_pipes``
    set.
    - If the edge is horizontal, check if the surface is attached to the top face
    of the pipe. If so, add the pipe to the ``top_readout_pipes`` set; otherwise,
    add the pipe to the ``bottom_stabilizer_pipes`` set.
    - For each cube in the pipe, check if the surface is attached to the top face
    of the cube. If so, add the cube to the ``top_readout_cubes`` set. Otherwise,
    add the pipe to the ``bottom_stabilizer_pipes`` set with the arms of the
    cubes in the pipe.

    Args:
        block_graph: The block graph whose corresponding ZX graph supports the
            correlation surface.
        correlation_surface: The correlation surface to convert into an abstract
            observable.
        include_temporal_hadamard_pipes: whether to include the temporal hadamard
            pipes in the observable. This is only relevant for the fixed bulk
            convention.

    Returns:
        The abstract observable corresponding to the correlation surface in the block graph.

    Raises:
        TQECError: If the block graph has open ports or the block graph cannot
            support the correlation surface.

    """
    # 0. Handle single node edge case
    if correlation_surface.is_single_node:
        # single stability experiment
        cube = block_graph.cubes[0]
        cube_with_arms = CubeWithArms(cube)
        if cube.is_spatial:
            return AbstractObservable(bottom_stabilizer_cubes=frozenset([cube_with_arms]))
        # single memory experiment
        return AbstractObservable(top_readout_cubes=frozenset([cube_with_arms]))

    pg = block_graph.to_zx_graph()
    _check_correlation_surface_validity(correlation_surface, pg.g)

    endpoints_to_edge: dict[frozenset[Position3D], list[ZXEdge]] = {}
    for edge in correlation_surface.span:
        u, v = edge.u.id, edge.v.id
        endpoints = frozenset({pg[u], pg[v]})
        endpoints_to_edge.setdefault(endpoints, []).append(edge)

    top_readout_cubes: set[CubeWithArms] = set()
    top_readout_pipes: set[PipeWithArms] = set()
    bottom_stabilizer_pipes: set[PipeWithArms] = set()
    temporal_hadamard_pipes: set[PipeWithObservableBasis] = set()

    # 1. Handle spatial cubes top readouts
    for node in correlation_surface.span_vertices():
        cube = block_graph[pg[node]]
        if not cube.is_spatial:
            continue

        kind = cube.kind
        assert isinstance(kind, ZXCube)
        bases = correlation_surface.bases_at(node)
        normal_basis = kind.normal_basis
        # correlation surface parallel to the normal direction of the cube
        # accounts for the top readout measurements
        # we need to record the arm flags to specify different shapes of the
        # observable lines, e.g. L-shape, 7-shape, -- shape, etc.
        if {normal_basis.flipped()} != bases:
            # check correlation edges in the cube arms
            arms = SpatialArms.NONE
            for arm, shift in SpatialArms.get_map_from_arm_to_shift().items():
                edges = endpoints_to_edge.get(
                    frozenset({cube.position, cube.position.shift_by(*shift)})
                )
                if edges is not None and any(
                    n.basis == normal_basis for edge in edges for n in edge
                ):
                    arms |= arm
            assert len(arms) in {
                2,
                4,
            }, "The correlation parity should be even for parallel correlation surface."
            # Two separate lines in the cube
            # By convention, we always split the four arms into [LEFT | DOWN] and [RIGHT | UP]
            if len(arms) == 4:
                top_readout_cubes.add(CubeWithArms(cube, SpatialArms.LEFT | SpatialArms.DOWN))
                top_readout_cubes.add(CubeWithArms(cube, SpatialArms.RIGHT | SpatialArms.UP))
            else:
                top_readout_cubes.add(CubeWithArms(cube, arms))

    # 2. Handle all the pipes
    def has_obs_include(cube: Cube, correlation: Basis) -> bool:
        """Check if the top data qubit readout should be included in the observable."""
        if cube.is_y_cube:
            return True
        assert isinstance(cube.kind, ZXCube)
        # No pipe at the top
        if block_graph.has_pipe_between(cube.position, cube.position.shift_by(0, 0, 1)):
            return False
        # The correlation surface must be attached to the top face
        return cube.kind.z.value == correlation.value

    for edge in correlation_surface.span:
        up, vp = pg[edge.u.id], pg[edge.v.id]
        pipe = block_graph.get_pipe(up, vp)
        # Vertical pipes
        if pipe.direction == Direction3D.Z:
            # Temporal Hadamard might have measurements that should be included
            # during realignment of plaquettes under fixed-bulk convention
            if include_temporal_hadamard_pipes and pipe.kind.has_hadamard:
                temporal_hadamard_pipes.add(PipeWithObservableBasis(pipe, edge.u.basis))
            if has_obs_include(pipe.v, edge.v.basis):
                top_readout_cubes.add(CubeWithArms(pipe.v))
            continue
        arms_u = (
            SpatialArms.from_cube_in_graph(pipe.u, block_graph)
            if pipe.u.is_spatial
            else SpatialArms.NONE
        )
        arms_v = (
            SpatialArms.from_cube_in_graph(pipe.v, block_graph)
            if pipe.v.is_spatial
            else SpatialArms.NONE
        )
        # Horizontal pipes
        pipe_top_face = pipe.kind.z
        assert pipe_top_face is not None, "The pipe is guaranteed to be spatial."
        # There is correlation surface attached to the top of the pipe
        if pipe_top_face.value == edge.u.basis.value:
            top_readout_pipes.add(PipeWithArms(pipe, (arms_u, arms_v)))
            for cube, n in zip(pipe, edge):
                # Spatial cubes have already been handled
                if cube.is_spatial:
                    continue
                if has_obs_include(cube, n.basis):
                    top_readout_cubes.add(CubeWithArms(cube))
        else:
            bottom_stabilizer_pipes.add(PipeWithArms(pipe, (arms_u, arms_v)))

    return AbstractObservable(
        top_readout_cubes=frozenset(top_readout_cubes),
        top_readout_pipes=frozenset(top_readout_pipes),
        bottom_stabilizer_pipes=frozenset(bottom_stabilizer_pipes),
        temporal_hadamard_pipes=frozenset(temporal_hadamard_pipes),
    )


def _check_correlation_surface_validity(correlation_surface: CorrelationSurface, g: GraphS) -> None:
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.interop.pyzx.utils import is_boundary, is_s, is_z_no_phase  # noqa: PLC0415

    """Check the ZX graph can support the correlation surface."""
    # 1. Check the vertices in the correlation surface are in the graph
    if missing_vertices := (correlation_surface.span_vertices() - g.vertex_set()):
        raise TQECError(
            "The following vertices in the correlation surface are "
            f"not in the graph: {missing_vertices} "
        )
    # 2. Check the edges in the correlation surface are in the graph
    edges = g.edge_set()  # type: ignore
    for edge in correlation_surface.span:
        e = (edge.u.id, edge.v.id)
        if e not in edges and (e[1], e[0]) not in edges:
            raise TQECError(f"Edge {e} in the correlation surface is not in the graph.")
    # 3. Check parity around each vertex
    for v in correlation_surface.span_vertices():
        if is_boundary(g, v):
            continue
        edges = correlation_surface.edges_at(v)
        paulis: list[Basis] = [edge.u.basis if edge.u.id == v else edge.v.basis for edge in edges]
        counts = Counter(paulis)
        # Y vertex should have Y pauli
        if is_s(g, v):
            if counts[Basis.X] != 1 or counts[Basis.Z] != 1:
                raise TQECError(
                    f"Y type vertex should have Pauli Y supported on it, {v} violates the rule."
                )
            continue
        v_basis = Basis.Z if is_z_no_phase(g, v) else Basis.X
        if counts[v_basis.flipped()] not in [0, len(g.incident_edges(v))]:  # type: ignore
            raise TQECError(
                "X (Z) type vertex should have Pauli Z (X) Pauli supported on "
                f"all or no edges, {v} violates the rule."
            )
        if counts[v_basis] % 2 != 0:
            raise TQECError(
                f"X (Z) type vertex should have even number of Pauli X (Z) supported"
                f"on the edges, {v} violates the rule."
            )
