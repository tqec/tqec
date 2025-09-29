from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, cast

from tqec.compile.blocks.block import Block
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, CubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction


@dataclass(frozen=True)
class CubeSpec:
    """Specification of a cube in a block graph.

    The template of the `CompiledBlock` will be determined based on the specification.
    This class can be used as a key to look up the corresponding `CompiledBlock` before
    applying the substitution rules.

    Attributes:
        cube_kind: The kind of the cube.
        spatial_arms: Flag indicating the spatial directions the cube connects to the
            adjacent cubes. This is useful for spatial cubes (XXZ and ZZX) where
            the arms can determine the template used to implement the cube.
        has_spatial_up_or_down_pipe_in_timeslice: a flag indicating if a spatial
            pipe at the top or bottom of a spatial cube is executed on the same
            timeslice as this cube. This information is needed for the fixed
            boundary convention.

    """

    kind: CubeKind
    spatial_arms: SpatialArms = SpatialArms.NONE
    has_spatial_up_or_down_pipe_in_timeslice: bool = False

    def __post_init__(self) -> None:
        if self.spatial_arms != SpatialArms.NONE:
            if not self.is_spatial:
                raise TQECError(
                    "The `spatial_arms` attribute should be `SpatialArms.NONE` "
                    "for non-spatial cubes."
                )

    @property
    def is_spatial(self) -> bool:
        """Return ``True`` if ``self`` represents a spatial cube."""
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    @staticmethod
    def from_cube(
        cube: Cube,
        graph: BlockGraph,
        spatial_up_or_down_pipes_slices: frozenset[int] = frozenset(),
    ) -> CubeSpec:
        """Return the cube spec from a cube in a block graph."""
        has_spatial_up_or_down_pipe_in_timeslice = (
            cube.position.z in spatial_up_or_down_pipes_slices
        )
        if not cube.is_spatial:
            return CubeSpec(
                cube.kind,
                has_spatial_up_or_down_pipe_in_timeslice=has_spatial_up_or_down_pipe_in_timeslice,
            )
        spatial_arms = SpatialArms.from_cube_in_graph(cube, graph)
        return CubeSpec(cube.kind, spatial_arms, has_spatial_up_or_down_pipe_in_timeslice)

    @property
    def pipe_dimensions(self) -> frozenset[Literal[Direction3D.X, Direction3D.Y]]:
        """Return the dimension(s) in which ``self`` has at least one pipe."""
        dimensions: list[Literal[Direction3D.X, Direction3D.Y]] = []
        if SpatialArms.LEFT in self.spatial_arms or SpatialArms.RIGHT in self.spatial_arms:
            dimensions.append(Direction3D.X)
        if SpatialArms.UP in self.spatial_arms or SpatialArms.DOWN in self.spatial_arms:
            dimensions.append(Direction3D.Y)
        return cast(frozenset[Literal[Direction3D.X, Direction3D.Y]], frozenset(dimensions))

    @property
    def has_spatial_pipe_in_both_dimensions(self) -> bool:
        """Return ``True`` if the provided spec has a pipe in each of the two spatial dimensions."""
        return self.spatial_arms.has_spatial_arm_in_both_dimensions


class CubeBuilder(Protocol):
    """Protocol for building a `Block` based on a `CubeSpec`."""

    def __call__(self, spec: CubeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a ``Block`` instance from a ``CubeSpec``.

        Args:
            spec: Specification of the cube in the block graph.
            block_temporal_height: the number of rounds of stabilizer measurements
            (ignoring one layer for initialization and another for final measurement).

        Returns:
            a ``Block`` based on the provided ``CubeSpec``.

        """
        ...


class PipeBuilder(Protocol):
    """Protocol for building a `Block` based on a `PipeSpec`."""

    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a `CompiledBlock` instance from a `PipeSpec`.

        Args:
            spec: Specification of the cube in the block graph.
            block_temporal_height: the number of rounds of stabilizer measurements
            (ignoring one layer for initialization and another for final measurement).

        Returns:
            a `CompiledBlock` based on the provided `PipeSpec`.

        """
        ...


@dataclass(frozen=True)
class PipeSpec:
    """Specification of a pipe in a block graph.

    The `PipeSpec` is used to determine the substitution rules between the two
    `CompiledBlock`s connected by the pipe. The substitution rules are used to
    update the layers of the `CompiledBlock`s based on the plaquettes in the
    `Substitution`.

    Attributes:
        cube_specs: the ordered cube specifications. By convention, the cube
            corresponding to ``cube_specs[0]`` should have a smaller position
            than the cube corresponding to ``cube_specs[1]``.
        cube_templates: templates used to implement the respective entry in
            ``cube_specs``.
        pipe_type: the type of the pipe connecting the two cubes.
        has_spatial_up_or_down_pipe_in_timeslice: a flag indicating if a spatial
            pipe at the top or bottom of a spatial cube is executed on the same
            timeslice as this cube. This information is needed for the fixed
            boundary convention.
        at_temporal_hadamard_layer: flag indicating whether the pipe is a temporal
            pipe and there is a temporal Hadamard pipe at the same Z position
            in the block graph.

    """

    cube_specs: tuple[CubeSpec, CubeSpec]
    cube_templates: tuple[RectangularTemplate, RectangularTemplate]
    pipe_kind: PipeKind
    has_spatial_up_or_down_pipe_in_timeslice: bool = False
    at_temporal_hadamard_layer: bool = False
