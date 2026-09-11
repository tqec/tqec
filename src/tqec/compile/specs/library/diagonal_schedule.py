"""Cube and Pipe builders for diagonal schedule convention.

This module provides builders that use the diagonal schedule generator
for implementing surface code circuits with diagonal syndrome extraction.
"""

from __future__ import annotations

from typing_extensions import override

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.specs.base import (
    CubeBuilder,
    CubeSpec,
    PipeBuilder,
    PipeSpec,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.diagonal_schedule import (
    DiagonalScheduleGenerator,
    create_diagonal_schedule_compiler,
)
from tqec.computation.cube import Port, YHalfCube, ZXCube
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction


class DiagonalScheduleCubeBuilder(CubeBuilder):
    """Cube builder that uses the diagonal schedule generator."""
    
    def __init__(
        self,
        compiler: PlaquetteCompiler | None = None,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Initialize the diagonal schedule cube builder.
        
        Args:
            compiler: Plaquette compiler instance. Defaults to diagonal schedule compiler.
            translator: RPNG translator instance. Defaults to DefaultRPNGTranslator.
        """
        if compiler is None:
            compiler = create_diagonal_schedule_compiler()
        self._generator = DiagonalScheduleGenerator(translator, compiler)

    def _get_template_and_plaquettes(
        self, spec: CubeSpec
    ) -> tuple[RectangularTemplate, tuple[Plaquettes, Plaquettes, Plaquettes]]:
        """Get the template and plaquettes corresponding to the provided ``spec``.
        
        Args:
            spec: specification of the cube we want to implement.
            
        Returns:
            the template and list of 3 mappings from plaquette indices to Plaquettes
            that are needed to implement the cube corresponding to the provided ``spec``.
        """
        assert isinstance(spec.kind, ZXCube)
        x, _, z = spec.kind.as_tuple()
        if not spec.is_spatial:
            orientation = Orientation.HORIZONTAL if x == Basis.Z else Orientation.VERTICAL
            return self._generator.get_memory_qubit_raw_template(), (
                self._generator.get_memory_qubit_plaquettes(orientation, z, None),
                self._generator.get_memory_qubit_plaquettes(orientation, None, None),
                self._generator.get_memory_qubit_plaquettes(orientation, None, z),
            )
        # else: spatial cube
        # Spatial cube uses Z boundary basis for the spatial boundaries
        # The x basis here is actually the temporal boundary basis
        return self._generator.get_spatial_cube_qubit_raw_template(), (
            self._generator.get_spatial_cube_qubit_plaquettes(Basis.Z, spec.spatial_arms, z, None),
            self._generator.get_spatial_cube_qubit_plaquettes(Basis.Z, spec.spatial_arms, None, None),
            self._generator.get_spatial_cube_qubit_plaquettes(Basis.Z, spec.spatial_arms, None, z),
        )

    @override
    def __call__(self, spec: CubeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a block using diagonal schedule plaquettes."""
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECError("Cannot build a block for a Port.")
        elif isinstance(kind, YHalfCube):
            raise NotImplementedError("Y cube is not implemented.")
        # else
        template, (init, repeat, measure) = self._get_template_and_plaquettes(spec)
        layers: list[BaseLayer | BaseComposedLayer] = [
            PlaquetteLayer(template, init),
            RepeatedLayer(PlaquetteLayer(template, repeat), repetitions=block_temporal_height),
            PlaquetteLayer(template, measure),
        ]
        return Block(layers)


class DiagonalSchedulePipeBuilder(PipeBuilder):
    """Pipe builder that uses the diagonal schedule generator."""
    
    def __init__(
        self,
        compiler: PlaquetteCompiler | None = None,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Initialize the diagonal schedule pipe builder.
        
        Args:
            compiler: Plaquette compiler instance. Defaults to diagonal schedule compiler.
            translator: RPNG translator instance. Defaults to DefaultRPNGTranslator.
        """
        if compiler is None:
            compiler = create_diagonal_schedule_compiler()
        self._generator = DiagonalScheduleGenerator(translator, compiler)

    @override
    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> Block:
        """Build a pipe using diagonal schedule plaquettes."""
        if spec.pipe_kind.is_temporal:
            # For temporal pipes, delegate to fixed bulk builder
            from tqec.compile.specs.library.fixed_bulk import FixedBulkPipeBuilder
            from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
            original_builder = FixedBulkPipeBuilder(IdentityPlaquetteCompiler, DefaultRPNGTranslator())
            return original_builder(spec, block_temporal_height)
        
        # For Hadamard pipes (spatial pipes connecting non-spatial cubes), delegate to original
        # The spatial Hadamard functionality is handled by the fixed bulk builder
        if spec.pipe_kind.has_hadamard and not any(spec.is_spatial for spec in spec.cube_specs):
            from tqec.compile.specs.library.fixed_bulk import FixedBulkPipeBuilder
            from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
            original_builder = FixedBulkPipeBuilder(IdentityPlaquetteCompiler, DefaultRPNGTranslator())
            return original_builder(spec, block_temporal_height)
        
        # Spatial pipe
        x, y, z = spec.pipe_kind.x, spec.pipe_kind.y, spec.pipe_kind.z
        assert x is not None or y is not None
        spatial_boundary_basis: Basis = x if x is not None else y  # type: ignore
        
        # Get the arm(s)
        arms = self._get_spatial_cube_arms(spec)
        
        # Get template and plaquettes
        pipe_template = self._generator.get_spatial_cube_arm_raw_template(arms)
        initialisation_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            spatial_boundary_basis, arms, spec.cube_specs, z, None
        )
        temporal_bulk_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            spatial_boundary_basis, arms, spec.cube_specs, None, None
        )
        measurement_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            spatial_boundary_basis, arms, spec.cube_specs, None, z
        )
        
        return Block(
            [
                PlaquetteLayer(pipe_template, initialisation_plaquettes),
                RepeatedLayer(
                    PlaquetteLayer(pipe_template, temporal_bulk_plaquettes),
                    repetitions=block_temporal_height,
                ),
                PlaquetteLayer(pipe_template, measurement_plaquettes),
            ]
        )
    
    @staticmethod
    def _get_spatial_cube_arms(spec: PipeSpec) -> SpatialArms:
        """Return the arm(s) corresponding to the provided spec."""
        assert spec.pipe_kind.is_spatial
        assert any(spec.is_spatial for spec in spec.cube_specs)
        u, v = spec.cube_specs
        pipedir = spec.pipe_kind.direction
        arms = SpatialArms.NONE
        if u.is_spatial:
            arms |= SpatialArms.RIGHT if pipedir == Direction3D.X else SpatialArms.DOWN
        if v.is_spatial:
            arms |= SpatialArms.LEFT if pipedir == Direction3D.X else SpatialArms.UP
        return arms

