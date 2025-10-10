from collections.abc import Callable

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
from tqec.compile.specs.library.generators.fixed_bulk import (
    FixedBulkConventionGenerator,
)
from tqec.computation.cube import Port, YHalfCube, ZXCube
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction


class FixedBulkCubeBuilder(CubeBuilder):
    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Implement the :class:`.CubeBuilder` interface for the fixed bulk convention.

        This class provides an implementation following the fixed-bulk convention. This convention
        consists in the fact that the top-left most plaquette in the bulk always measures a known-
        basis stabilizer (Z-basis for this class).

        """
        self._generator = FixedBulkConventionGenerator(translator, compiler)

    def _get_template_and_plaquettes(
        self, spec: CubeSpec
    ) -> tuple[RectangularTemplate, tuple[Plaquettes, Plaquettes, Plaquettes]]:
        """Get the template and plaquettes corresponding to the provided ``spec``.

        Args:
            spec: specification of the cube we want to implement.

        Returns:
            the template and list of 3 mappings from plaquette indices to RPNG
            descriptions that are needed to implement the cube corresponding to
            the provided ``spec``.

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
        # else:
        return self._generator.get_spatial_cube_qubit_raw_template(), (
            self._generator.get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, z, None),
            self._generator.get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, None),
            self._generator.get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, z),
        )

    @override
    def __call__(self, spec: CubeSpec, block_temporal_height: LinearFunction) -> Block:
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


class FixedBulkPipeBuilder(PipeBuilder):
    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Implement the :class:`.PipeBuilder` interface for the fixed bulk convention.

        This class provides an implementation following the fixed-bulk convention. This convention
        consists in the fact that the top-left most plaquette in the bulk always measures a known-
        parity stabilizer (Z-basis for this class).

        """
        self._generator = FixedBulkConventionGenerator(translator, compiler)

    @override
    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> Block:
        if spec.pipe_kind.is_temporal:
            return self._get_temporal_pipe_block(spec)
        return self._get_spatial_pipe_block(spec, block_temporal_height)

    #######################
    #    TEMPORAL PIPE    #
    #######################

    def _get_temporal_pipe_block(self, spec: PipeSpec) -> Block:
        """Return the block to implement a temporal pipe based on the provided ``spec``.

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a temporal pipe.

        Raises:
            AssertionError: if ``spec`` does not represent a temporal junction.

        Returns:
            the block to implement a temporal pipe based on the
        provided ``spec``..

        """
        assert spec.pipe_kind.is_temporal
        if spec.pipe_kind.has_hadamard:
            return self._get_temporal_hadamard_pipe_block(spec)
        # Else, it is a regular temporal junction
        return self._get_temporal_non_hadamard_pipe_block(spec)

    def _get_temporal_non_hadamard_pipe_block(self, spec: PipeSpec) -> Block:
        """Return the block to implement a regular temporal junction without Hadamard transition.

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a regular (i.e., non-Hadamard) temporal pipe.

        Raises:
            AssertionError: if the provided ``pipe`` is not a temporal pipe, or
                if it contains a Hadamard transition.

        Returns:
            the block to implement the provided
            ``spec``.

        """
        assert spec.pipe_kind.is_temporal
        assert not spec.pipe_kind.has_hadamard

        z_observable_orientation = (
            Orientation.HORIZONTAL if spec.pipe_kind.x == Basis.Z else Orientation.VERTICAL
        )
        memory_plaquettes = self._generator.get_memory_qubit_plaquettes(
            z_observable_orientation, None, None
        )
        template = self._generator.get_memory_qubit_raw_template()
        return Block(
            [
                PlaquetteLayer(template, memory_plaquettes)
                for _ in range(3 if spec.at_temporal_hadamard_layer else 2)
            ]
        )

    def _get_temporal_hadamard_pipe_block(self, spec: PipeSpec) -> Block:
        """Return the block to implement a temporal Hadamard pipe.

        Note:
            This method performs the realignment and Hadamard transition at the
            end of the layer that appear first (i.e., temporally before the other,
            or in other words the one with a lower Z index).

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a Hadamard temporal pipe.

        Raises:
            AssertionError: if the provided ``pipe`` is not a temporal pipe, or
                if it is not a Hadamard transition.

        Returns:
            the block to implement the provided ``spec``.

        """
        assert spec.pipe_kind.is_temporal
        assert spec.pipe_kind.has_hadamard

        z_observable_orientation = (
            Orientation.HORIZONTAL if spec.pipe_kind.x == Basis.Z else Orientation.VERTICAL
        )
        memory_plaquettes_before = self._generator.get_memory_qubit_plaquettes(
            z_observable_orientation, None, None
        )
        realignment_plaquettes = self._generator.get_temporal_hadamard_realignment_plaquettes(
            z_observable_orientation
        )
        memory_plaquettes_after = self._generator.get_memory_qubit_plaquettes(
            z_observable_orientation.flip(), None, None
        )
        template = self._generator.get_temporal_hadamard_raw_template()
        return Block(
            [
                PlaquetteLayer(template, memory_plaquettes_before),
                PlaquetteLayer(template, realignment_plaquettes),
                PlaquetteLayer(template, memory_plaquettes_after),
            ]
        )

    ##############################
    #       SPATIAL PIPE         #
    ##############################
    @staticmethod
    def _get_spatial_cube_arms(spec: PipeSpec) -> SpatialArms:
        """Return the arm(s) corresponding to the provided ``spec``.

        Args:
            spec: pipe specification to get the arm(s) from.

        Raises:
            TQECError: if the provided ``spec`` is not a spatial pipe.

        Returns:
            the :class:`~tqec.compile.specs.enums.SpatialArms` instance
            corresponding to the provided ``spec``. The returned flag contains
            either one or two flags. If two flags are returned, they should be
            on the same line (e.g., it cannot be ``SpatialArms.RIGHT | SpatialArms.UP``
            but can be ``SpatialArms.RIGHT | SpatialArms.LEFT``).

        """
        assert spec.pipe_kind.is_spatial
        # Check that we do have a spatial junction.
        assert any(spec.is_spatial for spec in spec.cube_specs)
        u, v = spec.cube_specs
        pipedir = spec.pipe_kind.direction
        arms = SpatialArms.NONE
        if u.is_spatial:
            arms |= SpatialArms.RIGHT if pipedir == Direction3D.X else SpatialArms.DOWN
        if v.is_spatial:
            arms |= SpatialArms.LEFT if pipedir == Direction3D.X else SpatialArms.UP
        return arms

    def _get_spatial_cube_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        x, y, z = spec.pipe_kind.x, spec.pipe_kind.y, spec.pipe_kind.z
        assert x is not None or y is not None
        spatial_boundary_basis: Basis = x if x is not None else y  # type: ignore
        # Get the plaquette indices mappings
        arms = FixedBulkPipeBuilder._get_spatial_cube_arms(spec)
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

    def _get_spatial_regular_pipe_template(self, spec: PipeSpec) -> RectangularTemplate:
        """Return the template needed to implement the pipe representing the provided ``spec``."""
        assert spec.pipe_kind.is_spatial
        match spec.pipe_kind.direction, spec.pipe_kind.has_hadamard:
            case Direction3D.X, False:
                return self._generator.get_memory_vertical_boundary_raw_template()
            case Direction3D.X, True:
                return self._generator.get_spatial_vertical_hadamard_raw_template()
            case Direction3D.Y, False:
                return self._generator.get_memory_horizontal_boundary_raw_template()
            case Direction3D.Y, True:
                return self._generator.get_spatial_horizontal_hadamard_raw_template()
            case _:
                raise TQECError("Spatial pipes cannot have a direction equal to Direction3D.Z.")

    def _get_spatial_regular_pipe_plaquettes_factory(
        self, spec: PipeSpec
    ) -> Callable[[Basis | None, Basis | None], Plaquettes]:
        assert spec.pipe_kind.is_spatial
        match spec.pipe_kind.direction, spec.pipe_kind.has_hadamard:
            case Direction3D.X, False:
                # Non-Hadamard pipe in the X direction.
                z_observable_orientation = (
                    Orientation.HORIZONTAL if spec.pipe_kind.y == Basis.X else Orientation.VERTICAL
                )
                return lambda r, m: self._generator.get_memory_vertical_boundary_plaquettes(
                    z_observable_orientation, r, m
                )
            case Direction3D.X, True:
                # Hadamard pipe in the X direction.
                top_left_basis = spec.pipe_kind.get_basis_along(Direction3D.Y, at_head=True)
                return lambda r, m: self._generator.get_spatial_vertical_hadamard_plaquettes(
                    top_left_basis == Basis.Z, r, m
                )
            case Direction3D.Y, False:
                # Non-Hadamard pipe in the Y direction.
                z_observable_orientation = (
                    Orientation.HORIZONTAL if spec.pipe_kind.x == Basis.Z else Orientation.VERTICAL
                )
                return lambda r, m: self._generator.get_memory_horizontal_boundary_plaquettes(
                    z_observable_orientation, r, m
                )

            case Direction3D.Y, True:
                # Hadamard pipe in the Y direction.
                top_left_basis = spec.pipe_kind.get_basis_along(Direction3D.X, at_head=True)
                return lambda r, m: self._generator.get_spatial_horizontal_hadamard_plaquettes(
                    top_left_basis == Basis.Z, r, m
                )
            case _:
                raise TQECError("Spatial pipes cannot have a direction equal to Direction3D.Z.")

    def _get_spatial_regular_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        assert all(not spec.is_spatial for spec in spec.cube_specs)
        plaquettes_factory = self._get_spatial_regular_pipe_plaquettes_factory(spec)
        template = self._get_spatial_regular_pipe_template(spec)

        layers: list[BaseLayer | BaseComposedLayer] = [
            PlaquetteLayer(
                template,
                plaquettes_factory(spec.pipe_kind.z, None),
            ),
            RepeatedLayer(
                PlaquetteLayer(
                    template,
                    plaquettes_factory(None, None),
                ),
                repetitions=block_temporal_height,
            ),
            PlaquetteLayer(
                template,
                plaquettes_factory(None, spec.pipe_kind.z),
            ),
        ]
        return Block(layers)

    def _get_spatial_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        """Return the block to implement a spatial pipe based on the provided ``spec``.

        Args:
            spec: description of the pipe that should be implemented by this method. Should be a
                spatial pipe.
            block_temporal_height: the number of rounds of stabilizer measurements
            (ignoring one layer for initialization and another for final measurement).

        Raises:
            AssertionError: if ``spec`` does not represent a spatial pipe.

        Returns:
            the block to implement a spatial pipe based on the provided ``spec``.

        """
        assert spec.pipe_kind.is_spatial
        cube_specs = spec.cube_specs
        if cube_specs[0].is_spatial or cube_specs[1].is_spatial:
            return self._get_spatial_cube_pipe_block(spec, block_temporal_height)
        return self._get_spatial_regular_pipe_block(spec, block_temporal_height)


FIXED_BULK_CUBE_BUILDER: CubeBuilder = FixedBulkCubeBuilder(IdentityPlaquetteCompiler)
FIXED_BULK_PIPE_BUILDER: PipeBuilder = FixedBulkPipeBuilder(IdentityPlaquetteCompiler)
