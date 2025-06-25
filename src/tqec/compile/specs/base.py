from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tqec.compile.blocks.block import Block
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, CubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECException


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

    """

    kind: CubeKind
    spatial_arms: SpatialArms = SpatialArms.NONE

    def __post_init__(self) -> None:
        if self.spatial_arms != SpatialArms.NONE:
            if not self.is_spatial:
                raise TQECException(
                    "The `spatial_arms` attribute should be `SpatialArms.NONE` for non-spatial cubes."
                )

    @property
    def is_spatial(self) -> bool:
        """Return ``True`` if ``self`` represents a spatial cube."""
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    @staticmethod
    def from_cube(cube: Cube, graph: BlockGraph) -> CubeSpec:
        """Returns the cube spec from a cube in a block graph."""
        if not cube.is_spatial:
            return CubeSpec(cube.kind)
        pos = cube.position
        spatial_arms = SpatialArms.NONE
        for flag, shift in SpatialArms.get_map_from_arm_to_shift().items():
            if graph.has_pipe_between(pos, pos.shift_by(*shift)):
                spatial_arms |= flag
        return CubeSpec(cube.kind, spatial_arms)


class CubeBuilder(Protocol):
    """Protocol for building a `Block` based on a `CubeSpec`."""

    def __call__(self, spec: CubeSpec) -> Block:
        """Build a ``Block`` instance from a ``CubeSpec``.

        Args:
            spec: Specification of the cube in the block graph.

        Returns:
            a ``Block`` based on the provided ``CubeSpec``.

        """
        ...


class PipeBuilder(Protocol):
    """Protocol for building a `Block` based on a `PipeSpec`."""

    def __call__(self, spec: PipeSpec) -> Block:
        """Build a `CompiledBlock` instance from a `PipeSpec`.

        Args:
            spec: Specification of the cube in the block graph.

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
        at_temporal_hadamard_layer: flag indicating whether the pipe is a temporal
            pipe and there is a temporal Hadamard pipe at the same Z position
            in the block graph.

    """

    cube_specs: tuple[CubeSpec, CubeSpec]
    cube_templates: tuple[RectangularTemplate, RectangularTemplate]
    pipe_kind: PipeKind
    at_temporal_hadamard_layer: bool = False
