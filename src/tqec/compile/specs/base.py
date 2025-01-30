from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tqec.compile.block import CompiledBlock
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, CubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.plaquette.plaquette import Plaquettes
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
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    @staticmethod
    def from_cube(cube: Cube, graph: BlockGraph) -> CubeSpec:
        """Returns the cube spec from a cube in a block graph."""
        if not cube.is_spatial:
            return CubeSpec(cube.kind)
        pos = cube.position
        spatial_arms = SpatialArms.NONE
        for flag, shift in SpatialArms.get_map_from_arm_to_shift().items():
            if graph.has_edge_between(pos, pos.shift_by(*shift)):
                spatial_arms |= flag
        return CubeSpec(cube.kind, spatial_arms)


class BlockBuilder(Protocol):
    """Protocol for building a `CompiledBlock` based on a `CubeSpec`."""

    def __call__(self, spec: CubeSpec) -> CompiledBlock:
        """Build a `CompiledBlock` instance from a `CubeSpec`.

        Args:
            spec: Specification of the cube in the block graph.

        Returns:
            a `CompiledBlock` based on the provided `CubeSpec`.
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
    """

    cube_specs: tuple[CubeSpec, CubeSpec]
    cube_templates: tuple[RectangularTemplate, RectangularTemplate]
    pipe_kind: PipeKind


@dataclass(frozen=True)
class Substitution:
    """Collection of plaquettes categorized by the layer index.

    This specifies how to substitute plaquettes in the two `CompiledBlock`s
    connected by a pipe. When applying the substitution, the plaquettes in
    the map will be used to update the corresponding layer in the `CompiledBlock`.

    Both the source and destination maps are indexed by the layer index in the
    `CompiledBlock`. The index can be negative, which means the layer is counted
    from the end of the layers list.

    Attributes:
        src: a mapping from the index of the layer in the source `CompiledBlock` to
            the plaquettes that should be used to update the layer.
        dst: a mapping from the index of the layer in the destination `CompiledBlock`
            to the plaquettes that should be used to update
    """

    src: dict[int, Plaquettes]
    dst: dict[int, Plaquettes]


class SubstitutionBuilder(Protocol):
    """Protocol for building the `Substitution` based on a `PipeSpec`."""

    def __call__(self, spec: PipeSpec) -> Substitution:
        """Build a `Substitution` instance from a `PipeSpec`.

        Args:
            spec: Specification of the pipe in the block graph.

        Returns:
            a `Substitution` based on the provided `PipeSpec`.
        """
        ...
