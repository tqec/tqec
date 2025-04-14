from typing import Callable, Final

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.base import (
    CubeBuilder,
    CubeSpec,
    PipeBuilder,
    PipeSpec,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.fixed_parity import (
    FixedParityConventionGenerator,
)
from tqec.computation.cube import Port, YHalfCube, ZXCube
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction

_DEFAULT_BLOCK_REPETITIONS: Final[LinearFunction] = LinearFunction(2, -1)


class FixedParityCubeBuilder(CubeBuilder):
    """Implementation of the :class:`~tqec.compile.specs.base.CubeBuilder`
    interface for the fixed parity convention.

    This class provides an implementation following the fixed-parity convention.
    This convention consists in the fact that 2-body stabilizers on the boundary
    of a logical qubit are always at an even parity.
    """

    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        self._generator = FixedParityConventionGenerator(translator, compiler)

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
            orientation = (
                Orientation.HORIZONTAL if x == Basis.Z else Orientation.VERTICAL
            )
            return self._generator.get_memory_qubit_raw_template(), (
                self._generator.get_memory_qubit_plaquettes(orientation, z, None),
                self._generator.get_memory_qubit_plaquettes(orientation, None, None),
                self._generator.get_memory_qubit_plaquettes(orientation, None, z),
            )
        # else:
        SA = spec.spatial_arms
        return self._generator.get_spatial_cube_qubit_raw_template(), (
            self._generator.get_spatial_cube_qubit_plaquettes(x, SA, z, None),
            self._generator.get_spatial_cube_qubit_plaquettes(x, SA, None, None),
            self._generator.get_spatial_cube_qubit_plaquettes(x, SA, None, z),
        )

    def __call__(self, spec: CubeSpec) -> Block:
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECException("Cannot build a block for a Port.")
        elif isinstance(kind, YHalfCube):
            raise NotImplementedError("Y cube is not implemented.")
        # else
        template, (init, repeat, measure) = self._get_template_and_plaquettes(spec)
        layers: list[BaseLayer | BaseComposedLayer] = [
            PlaquetteLayer(template, init),
            RepeatedLayer(
                PlaquetteLayer(template, repeat), repetitions=_DEFAULT_BLOCK_REPETITIONS
            ),
            PlaquetteLayer(template, measure),
        ]
        return Block(layers)


class FixedParityPipeBuilder(PipeBuilder):
    """Implementation of the :class:`~tqec.compile.specs.base.PipeBuilder`
    interface for the fixed parity convention.

    This class provides an implementation following the fixed-parity convention.
    This convention consists in the fact that 2-body stabilizers on the boundary
    of a logical qubit are always at an even parity.
    """

    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        self._generator = FixedParityConventionGenerator(translator, compiler)

    def __call__(self, spec: PipeSpec) -> Block:
        if spec.pipe_kind.is_temporal:
            return self.get_temporal_pipe_block(spec)
        return self.get_spatial_pipe_block(spec)

    #######################
    #    TEMPORAL PIPE    #
    #######################
    def get_temporal_pipe_block(self, spec: PipeSpec) -> Block:
        """Returns the block to implement a temporal pipe based on the
        provided ``spec``.

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a temporal pipe.

        Raises:
            AssertionError: if ``spec`` does not represent a temporal pipe.

        Returns:
            the block to implement a temporal pipe based on the provided
            ``spec``.
        """
        assert spec.pipe_kind.is_temporal
        z_orientation = (
            Orientation.HORIZONTAL
            if spec.pipe_kind.x == Basis.Z
            else Orientation.VERTICAL
        )
        memory_template = self._generator.get_memory_qubit_raw_template()
        memory_plaquettes = self._generator.get_memory_qubit_plaquettes(
            z_orientation, None, None
        )
        memory_layer = PlaquetteLayer(memory_template, memory_plaquettes)

        if spec.pipe_kind.has_hadamard:
            hadamard_template = self._generator.get_temporal_hadamard_raw_template()
            hadamard_plaquettes = self._generator.get_temporal_hadamard_plaquettes(
                z_orientation
            )
            hadamard_layer = PlaquetteLayer(hadamard_template, hadamard_plaquettes)
            return Block([hadamard_layer, memory_layer])
        # Else, it is a regular temporal junction
        return Block([memory_layer for _ in range(2)])

    ##############################
    #       SPATIAL PIPE         #
    ##############################
    @staticmethod
    def _get_spatial_cube_arms(spec: PipeSpec) -> SpatialArms:
        """Returns the arm(s) corresponding to the provided ``spec``.

        Args:
            spec: pipe specification to get the arm(s) from.

        Raises:
            TQECException: if the provided ``spec`` is not a spatial pipe.

        Returns:
            the :class:`~tqec.compile.specs.enums.SpatialArms` instance
            corresponding to the provided ``spec``. The returned flag contains
            either one or two flags. If two flags are returned, they should be
            on the same line (e.g., it cannot be ``SpatialArms.RIGHT | SpatialArms.UP``
            but can be ``SpatialArms.RIGHT | SpatialArms.LEFT``).

            For example, if ``SpatialArms.LEFT`` is in the returned ``SpatialArms``
            flag, that means that the pipe represented by the provided ``spec``
            is the left arm of a spatial cube.
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

    def _get_spatial_cube_pipe_block(self, spec: PipeSpec) -> Block:
        x, y, z = spec.pipe_kind.x, spec.pipe_kind.y, spec.pipe_kind.z
        assert x is not None or y is not None
        spatial_boundary_basis: Basis = x if x is not None else y  # type: ignore
        # Get the plaquette indices mappings
        arms = FixedParityPipeBuilder._get_spatial_cube_arms(spec)
        pipe_template = self._generator.get_spatial_cube_arm_raw_template(arms)
        SBB = spatial_boundary_basis
        initialisation_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            SBB, arms, spec.cube_specs, is_reversed=False, reset=z, measurement=None
        )
        reversed_memory_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            SBB, arms, spec.cube_specs, is_reversed=True, reset=None, measurement=None
        )
        forward_memory_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            SBB, arms, spec.cube_specs, is_reversed=False, reset=None, measurement=None
        )
        measurement_plaquettes = self._generator.get_spatial_cube_arm_plaquettes(
            SBB, arms, spec.cube_specs, is_reversed=False, reset=None, measurement=z
        )
        _expected_reps = LinearFunction(2, -1)
        if _DEFAULT_BLOCK_REPETITIONS != _expected_reps:
            raise NotImplementedError(
                "Not implemented for a number of temporal repetitions != "
                f"{_expected_reps}. Got {_DEFAULT_BLOCK_REPETITIONS}."
            )
        forward_layer = PlaquetteLayer(pipe_template, forward_memory_plaquettes)
        reversed_layer = PlaquetteLayer(pipe_template, reversed_memory_plaquettes)
        return Block(
            [
                PlaquetteLayer(pipe_template, initialisation_plaquettes),
                SequencedLayers(
                    [
                        RepeatedLayer(
                            SequencedLayers([reversed_layer, forward_layer]),
                            repetitions=LinearFunction(1, -1),
                        ),
                        reversed_layer,
                    ]
                ),
                PlaquetteLayer(pipe_template, measurement_plaquettes),
            ]
        )

    def _get_spatial_regular_pipe_template(self, spec: PipeSpec) -> RectangularTemplate:
        """Returns the ``Template`` instance needed to implement the pipe
        representing the provided ``spec``."""
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
                raise TQECException(
                    "Spatial pipes cannot have a direction equal to Direction3D.Z."
                )

    def _get_spatial_regular_non_hadamard_pipe_plaquettes_factory(
        self, spec: PipeSpec
    ) -> Callable[[Basis | None, Basis | None], Plaquettes]:
        if spec.pipe_kind.direction == Direction3D.X:
            # Pipe between two cubes aligned on the X axis
            z_observable_orientation = (
                Orientation.HORIZONTAL
                if spec.pipe_kind.y == Basis.X
                else Orientation.VERTICAL
            )
            return lambda r, m: self._generator.get_memory_vertical_boundary_plaquettes(
                z_observable_orientation, r, m
            )
        # Else, pipe between two cubes aligned on the Y axis
        z_observable_orientation = (
            Orientation.HORIZONTAL
            if spec.pipe_kind.x == Basis.Z
            else Orientation.VERTICAL
        )
        return lambda r, m: self._generator.get_memory_horizontal_boundary_plaquettes(
            z_observable_orientation, r, m
        )

    def _get_spatial_regular_pipe_plaquettes_factory(
        self, spec: PipeSpec
    ) -> Callable[[Basis | None, Basis | None], Plaquettes]:
        assert spec.pipe_kind.is_spatial
        if not spec.pipe_kind.has_hadamard:
            return self._get_spatial_regular_non_hadamard_pipe_plaquettes_factory(spec)
        # Else, a Hadamard pipe.
        pipe_in_x_direction = spec.pipe_kind.direction == Direction3D.X
        top_left_basis = (
            spec.pipe_kind.get_basis_along(Direction3D.Y, at_head=True)
            if pipe_in_x_direction
            else spec.pipe_kind.get_basis_along(Direction3D.X, at_head=True)
        )
        assert top_left_basis is not None
        if pipe_in_x_direction:
            # Hadamard pipe between two cubes aligned on the X axis
            return (
                lambda r, m: self._generator.get_spatial_vertical_hadamard_plaquettes(
                    top_left_basis, r, m
                )
            )
        # Else, Hadamard pipe between two cubes aligned on the Y axis
        return lambda r, m: self._generator.get_spatial_horizontal_hadamard_plaquettes(
            top_left_basis, r, m
        )

    def _get_spatial_regular_pipe_block(self, spec: PipeSpec) -> Block:
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
                repetitions=_DEFAULT_BLOCK_REPETITIONS,
            ),
            PlaquetteLayer(
                template,
                plaquettes_factory(None, spec.pipe_kind.z),
            ),
        ]
        return Block(layers)

    def get_spatial_pipe_block(self, spec: PipeSpec) -> Block:
        assert spec.pipe_kind.is_spatial
        cube_specs = spec.cube_specs
        if cube_specs[0].is_spatial or cube_specs[1].is_spatial:
            return self._get_spatial_cube_pipe_block(spec)
        return self._get_spatial_regular_pipe_block(spec)


FIXED_PARITY_CUBE_BUILDER = FixedParityCubeBuilder(IdentityPlaquetteCompiler)
FIXED_PARITY_PIPE_BUILDER = FixedParityPipeBuilder(IdentityPlaquetteCompiler)
