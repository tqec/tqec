from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, cast

from tqec.compile.blocks.block import Block, LayeredBlock
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, CubeKind, YHalfCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction


@dataclass(frozen=True)
class YHalfCubeSpec:
    """Specification of a Y half cube in a block graph.

    Attributes:
        initialization: Flag indicating whether the half cube is for Y-basis
            initialization or measurement.
        horizontal_boundary_basis: The basis of the horizontal boundary of the
            pipe connecting to the cube.

    """

    initialization: bool
    horizontal_boundary_basis: Basis

    @staticmethod
    def from_cube(
        cube: Cube,
        graph: BlockGraph,
    ) -> YHalfCubeSpec:
        """Return the spec from a Y half cube in a block graph."""
        pos = cube.position
        pos_up, pos_down = pos.shift_by(dz=1), pos.shift_by(dz=-1)
        connect_up = graph.has_pipe_between(pos, pos_up)
        connect_down = graph.has_pipe_between(pos, pos_down)
        assert connect_down + connect_up == 1
        if connect_up:
            pipe = graph.get_pipe(pos, pos_up)
            at_head = True
        else:
            pipe = graph.get_pipe(pos, pos_down)
            at_head = False

        horizontal_boundary_basis = pipe.kind.get_basis_along(Direction3D.Y, at_head)
        assert horizontal_boundary_basis is not None
        return YHalfCubeSpec(
            initialization=connect_up,
            horizontal_boundary_basis=horizontal_boundary_basis,
        )


@dataclass(frozen=True)
class CubeSpec:
    """Specification of a cube in a block graph.

    The block instantiation will be determined based on the specification.

    Attributes:
        cube_kind: The kind of the cube.
        spatial_arms: Flag indicating the spatial directions the cube connects to the
            adjacent cubes. This is useful for spatial cubes (XXZ and ZZX) where
            the arms can determine the template used to implement the cube.
        has_spatial_up_or_down_pipe_in_timeslice: a flag indicating if a spatial
            pipe at the top or bottom of a spatial cube is executed on the same
            timeslice as this cube. This information is needed for the fixed
            boundary convention.
        y_half_cube_spec: If the cube is a Y half cube, this attribute contains
            the specification of the half cube. Otherwise, it is ``None``.

    """

    kind: CubeKind
    spatial_arms: SpatialArms = SpatialArms.NONE
    has_spatial_up_or_down_pipe_in_timeslice: bool = False
    y_half_cube_spec: YHalfCubeSpec | None = None

    def __post_init__(self) -> None:
        if self.spatial_arms != SpatialArms.NONE:
            if not self.is_spatial:
                raise TQECError(
                    "The `spatial_arms` attribute should be `SpatialArms.NONE` "
                    "for non-spatial cubes."
                )
        if isinstance(self.kind, YHalfCube) != (self.y_half_cube_spec is not None):
            raise TQECError(
                "The ``y_half_cube_spec`` attribute should be set if and only if "
                "the cube is a ``YHalfCube``."
            )

    @property
    def is_spatial(self) -> bool:
        """Return ``True`` if ``self`` represents a spatial cube."""
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    @property
    def is_y_cube(self) -> bool:
        """Return ``True`` if ``self`` represents a ``YHalfCube``."""
        return isinstance(self.kind, YHalfCube)

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
        if cube.is_y_cube:
            y_spec = YHalfCubeSpec.from_cube(cube, graph)
            return CubeSpec(
                cube.kind,
                has_spatial_up_or_down_pipe_in_timeslice=has_spatial_up_or_down_pipe_in_timeslice,
                y_half_cube_spec=y_spec,
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

    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> LayeredBlock:
        """Build a ``LayeredBlock`` instance from a ``PipeSpec``.

        Args:
            spec: Specification of the pipe in the block graph.
            block_temporal_height: the number of rounds of stabilizer measurements
            (ignoring one layer for initialization and another for final measurement).

        Returns:
            a ``LayeredBlock`` based on the provided `PipeSpec`.

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
