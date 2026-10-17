from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from tqec.compile.blocks.block import Block
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, CubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, SignedDirection3D
from tqec.utils.scale import LinearFunction


@dataclass(frozen=True)
class CubeContextKey:
    """Hashable key describing the temporal context of a cube."""

    has_bottom_temporal_pipe: bool
    has_top_temporal_pipe: bool


@dataclass(frozen=True)
class CubeContext:
    """Read-only view of a cube and its surrounding block graph."""

    graph: BlockGraph = field(compare=False, hash=False, repr=False)
    cube: Cube

    def neighbour(self, d: SignedDirection3D) -> Cube | None:
        """Return the neighbouring cube in the given direction, if present."""
        position = self.cube.position.shift_in_direction(
            d.direction, 1 if d.towards_positive else -1
        )
        return self.graph[position] if position in self.graph else None

    def has_spatial_pipe(self, d: SignedDirection3D) -> bool:
        """Return whether a spatial pipe exists in the given direction."""
        if d.direction not in Direction3D.spatial_directions():
            raise TQECError("Expected a spatial direction (X or Y).")
        return self._has_pipe(d)

    def has_temporal_pipe(self, towards_positive: bool) -> bool:
        """Return whether a temporal pipe exists in the given direction."""
        return self._has_pipe(SignedDirection3D(Direction3D.Z, towards_positive))

    def _has_pipe(self, d: SignedDirection3D) -> bool:
        """Return whether a pipe connects this cube to its neighbour."""
        position = self.cube.position
        neighbour_position = position.shift_in_direction(
            d.direction, 1 if d.towards_positive else -1
        )
        return self.graph.has_pipe_between(position, neighbour_position)

    def key(self) -> CubeContextKey:
        """Return the hashable temporal-context key for this cube."""
        return CubeContextKey(
            has_bottom_temporal_pipe=self.has_temporal_pipe(False),
            has_top_temporal_pipe=self.has_temporal_pipe(True),
        )


@dataclass(frozen=True)
class CubeSpec:
    """Specification of a cube in a block graph.

    The template of the CompiledBlock is determined based on the specification.
    This class can be used as a key to look up the corresponding CompiledBlock
    before applying the substitution rules.

    Attributes:
        kind: The kind of the cube.
        spatial_arms: The spatial directions the cube connects to adjacent cubes.
            This is useful for spatial cubes where the arms determine the template.
        has_spatial_up_or_down_pipe_in_timeslice: Whether a spatial pipe at the
            top or bottom of a spatial cube is executed on the same timeslice
            as this cube. This is needed for the fixed boundary convention.

    """

    kind: CubeKind
    spatial_arms: SpatialArms = SpatialArms.NONE
    has_spatial_up_or_down_pipe_in_timeslice: bool = False

    def __post_init__(self) -> None:
        if self.spatial_arms != SpatialArms.NONE and not self.is_spatial:
            raise TQECError(
                "The `spatial_arms` attribute should be `SpatialArms.NONE` for non-spatial cubes."
            )

    @property
    def is_spatial(self) -> bool:
        """Return True if this specification represents a spatial cube."""
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    @staticmethod
    def from_cube(
        cube: Cube,
        graph: BlockGraph,
        spatial_up_or_down_pipes_slices: frozenset[int] = frozenset(),
    ) -> CubeSpec:
        """Return the cube specification for a cube in a block graph."""
        has_spatial_up_or_down_pipe_in_timeslice = (
            cube.position.z in spatial_up_or_down_pipes_slices
        )

        if not cube.is_spatial:
            return CubeSpec(
                cube.kind,
                has_spatial_up_or_down_pipe_in_timeslice=(has_spatial_up_or_down_pipe_in_timeslice),
            )

        spatial_arms = SpatialArms.from_cube_in_graph(cube, graph)
        return CubeSpec(
            cube.kind,
            spatial_arms,
            has_spatial_up_or_down_pipe_in_timeslice=(has_spatial_up_or_down_pipe_in_timeslice),
        )

    @property
    def pipe_dimensions(
        self,
    ) -> frozenset[Literal[Direction3D.X, Direction3D.Y]]:
        """Return the dimensions in which this cube has at least one pipe."""
        dimensions: list[Literal[Direction3D.X, Direction3D.Y]] = []

        if SpatialArms.LEFT in self.spatial_arms or SpatialArms.RIGHT in self.spatial_arms:
            dimensions.append(Direction3D.X)

        if SpatialArms.UP in self.spatial_arms or SpatialArms.DOWN in self.spatial_arms:
            dimensions.append(Direction3D.Y)

        return frozenset(dimensions)

    @property
    def has_spatial_pipe_in_both_dimensions(self) -> bool:
        """Return whether this cube has a pipe in both spatial dimensions."""
        return self.spatial_arms.has_spatial_arm_in_both_dimensions


class CubeBuilder(Protocol):
    """Protocol for building a Block based on a CubeSpec."""

    def __call__(self, spec: CubeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a Block instance from a CubeSpec.

        Args:
            spec: Specification of the cube in a block graph.
            block_temporal_height: Number of rounds of stabilizer measurements,
                ignoring one layer for initialization and another for final
                measurement.

        Returns:
            A Block based on the specification.

        """
        ...


class PipeBuilder(Protocol):
    """Protocol for building a Block based on a PipeSpec."""

    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a Block instance from a PipeSpec.

        Args:
            spec: Specification of the pipe in a block graph.
            block_temporal_height: Number of rounds of stabilizer measurements,
                ignoring one layer for initialization and another for final
                measurement.

        Returns:
            A Block based on the specification.

        """
        ...


@dataclass(frozen=True)
class PipeSpec:
    """Specification of a pipe in a block graph.

    The PipeSpec determines the substitution rules between the two compiled
    blocks connected by the pipe.

    Attributes:
        cube_specs: Ordered cube specifications. The first cube has a smaller
            position than the second cube.
        cube_templates: Templates used to implement the respective cube specs.
        pipe_kind: The type of pipe connecting the two cubes.
        context_keys: Temporal context keys for the two endpoint cubes.
        has_spatial_up_or_down_pipe_in_timeslice: Whether a spatial pipe at the
            top or bottom of a spatial cube is executed on the same timeslice.
        at_temporal_hadamard_layer: Whether this is a temporal pipe at a layer
            containing a temporal Hadamard pipe.

    """

    cube_specs: tuple[CubeSpec, CubeSpec]
    cube_templates: tuple[RectangularTemplate, RectangularTemplate]
    pipe_kind: PipeKind
    context_keys: tuple[CubeContextKey, CubeContextKey] | None = None
    has_spatial_up_or_down_pipe_in_timeslice: bool = False
    at_temporal_hadamard_layer: bool = False
