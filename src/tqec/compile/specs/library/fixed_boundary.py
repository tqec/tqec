from collections.abc import Callable
from typing import Protocol

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.base import CubeBuilder, CubeSpec, PipeBuilder, PipeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.fixed_boundary import FixedBoundaryConventionGenerator
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


class _PlaquettesGenerator(Protocol):
    def __call__(
        self, reversed: bool, reset: Basis | None, measurement: Basis | None, /
    ) -> Plaquettes: ...


def _get_block(
    z_basis: Basis | None,
    has_spatial_junction_in_timeslice: bool,
    template: RectangularTemplate,
    plaquettes_generator: _PlaquettesGenerator,
    repetitions: LinearFunction,
) -> Block:
    """Get the block implemented with the provided ``template`` and ``plaquettes_generator``.

    This helper function handles all the complexity linked to generating a :class:`.Block` instance
    for the fixed boundary convention, especially when a spatial junction needs to be implemented
    with alternating plaquettes where it handles the alternation correctly even in REPEAT blocks.

    Raises:
        TQECError: if ``repetitions.slope`` is not even. This function requires an even
            repetition slope because 1) the implementation for odd slopes is more complex and
            requires the implementation of more classes and 2) all the repetitions we have at the
            moment have an even slope.

    """
    # Naming convention: {f,b}{init,memory,meas}
    # f: forward
    # b: backward
    # init: initialisation plaquette (with data-qubit resets)
    # memory: memory plaquette (no data-qubit reset/measurement)
    # meas: measurement plaquette (with data-qubit measurements)
    finit = plaquettes_generator(False, z_basis, None)
    fmemory = plaquettes_generator(False, None, None)
    fmeas = plaquettes_generator(False, None, z_basis)
    bmemory = plaquettes_generator(True, None, None)
    bmeas = plaquettes_generator(True, None, z_basis)

    if not has_spatial_junction_in_timeslice:
        return Block(
            [
                PlaquetteLayer(template, finit),
                RepeatedLayer(PlaquetteLayer(template, fmemory), repetitions),
                PlaquetteLayer(template, fmeas),
            ]
        )
    # else
    # Here, we need to implement the block by alternating forward/backward
    # schedules. To do so, we need to repeat the REPEAT block body only half the
    # initial number of repetitions. Basically, we need to compute
    # `repetitions // 2` and `repetitions % 2`. The problem is that a simple
    # `LinearFunction` instance is not enough to encode the result of these
    # operations. See for example `LinearFunction(3, 0) // 2` that should give
    # `1` for `k=1`, `3` for `k=2` and `4` for `k=3`. These three points are
    # not forming a straight line, so a `LinearFunction` instance cannot
    # represent them. Circumventing this issue could be done by adding more
    # classes (e.g., ModFunction), but it seems simpler for the moment to just
    # raise on unsupported inputs.
    if repetitions.slope % 2 == 1:
        raise NotImplementedError(
            "Cannot have an odd slope for the number of repetitions when a "
            "spatial junction is present."
        )
    halved_repetitions = LinearFunction(repetitions.slope // 2, repetitions.offset // 2)
    remainder = repetitions.offset % 2
    loop_replacement: list[BaseLayer | BaseComposedLayer] = [
        RepeatedLayer(
            SequencedLayers([PlaquetteLayer(template, bmemory), PlaquetteLayer(template, fmemory)]),
            halved_repetitions,
        )
    ]
    if remainder == 1:  # Note that remainder can only be 0 or 1.
        loop_replacement.append(PlaquetteLayer(template, bmemory))

    return Block(
        [
            PlaquetteLayer(template, finit),
            SequencedLayers(loop_replacement),
            PlaquetteLayer(template, fmeas if remainder == 1 else bmeas),
        ]
    )


class FixedBoundaryCubeBuilder(CubeBuilder):
    def __init__(
        self, compiler: PlaquetteCompiler, translator: RPNGTranslator = DefaultRPNGTranslator()
    ) -> None:
        """Implement the :class:`.CubeBuilder` interface for the fixed boundary convention.

        This class provides an implementation following the fixed-boundary convention.
        This convention consists in the fact that 2-body stabilizers on the boundary
        of a logical qubit are always at an even position(counting clockwise from the
        top left corner starting at 1).

        Args:
            compiler: compiler used to compile :class:`.Plaquette` instances returned from the
                provided ``translator``.
            translator: translator to obtain :class:`.Plaquette` instances from a RPNG description.

        """
        self._generator = FixedBoundaryConventionGenerator(translator, compiler)

    def _get_template_and_plaquettes_generator(
        self, spec: CubeSpec
    ) -> tuple[RectangularTemplate, _PlaquettesGenerator]:
        assert isinstance(spec.kind, ZXCube)
        x = spec.kind.x
        if not spec.is_spatial:
            orientation = Orientation.HORIZONTAL if x == Basis.Z else Orientation.VERTICAL

            def _memory_plaquettes_generator(
                is_reversed: bool, r: Basis | None, m: Basis | None
            ) -> Plaquettes:
                return self._generator.get_memory_qubit_plaquettes(is_reversed, orientation, r, m)

            return (
                self._generator.get_memory_qubit_raw_template(),
                _memory_plaquettes_generator,
            )

        # else
        def _spatial_plaquettes_generator(
            is_reversed: bool, r: Basis | None, m: Basis | None
        ) -> Plaquettes:
            return self._generator.get_spatial_cube_qubit_plaquettes(
                x, spec.spatial_arms, is_reversed, r, m
            )

        return (
            self._generator.get_spatial_cube_qubit_raw_template(),
            _spatial_plaquettes_generator,
        )

    def __call__(self, spec: CubeSpec, block_temporal_height: LinearFunction) -> Block:
        """Instantiate a :class:`.Block` instance implementing the provided ``spec``."""
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECError("Cannot build a block for a Port.")
        elif isinstance(kind, YHalfCube):
            raise NotImplementedError("Y cube is not implemented.")
        template, pgen = self._get_template_and_plaquettes_generator(spec)
        return _get_block(
            z_basis=kind.z,
            has_spatial_junction_in_timeslice=spec.has_spatial_up_or_down_pipe_in_timeslice,
            template=template,
            plaquettes_generator=pgen,
            repetitions=block_temporal_height,
        )


class FixedBoundaryPipeBuilder(PipeBuilder):
    def __init__(
        self, compiler: PlaquetteCompiler, translator: RPNGTranslator = DefaultRPNGTranslator()
    ) -> None:
        """Implement the :class:`.PipeBuilder` interface for the fixed boundary convention.

        This class provides an implementation following the fixed-boundary convention.
        This convention consists in the fact that 2-body stabilizers on the boundary
        of a logical qubit are always at an even position(counting clockwise from the
        top left corner starting at 1).

        Args:
            compiler: compiler used to compile :class:`.Plaquette` instances returned from the
                provided ``translator``.
            translator: translator to obtain :class:`.Plaquette` instances from a RPNG description.

        """
        self._generator = FixedBoundaryConventionGenerator(translator, compiler)

    def __call__(self, spec: PipeSpec, block_temporal_height: LinearFunction) -> Block:
        """Instantiate a :class:`.Block` instance implementing the provided ``spec``."""
        if spec.pipe_kind.is_temporal:
            return self.get_temporal_pipe_block(spec)
        return self.get_spatial_pipe_block(spec, block_temporal_height)

    #######################
    #    TEMPORAL PIPE    #
    #######################
    def get_temporal_pipe_block(self, spec: PipeSpec) -> Block:
        """Return the block to implement a temporal pipe based on the provided ``spec``.

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
        hadamard_transition = spec.pipe_kind.has_hadamard
        z_orientation = (
            Orientation.HORIZONTAL if spec.pipe_kind.x == Basis.Z else Orientation.VERTICAL
        )
        memory_template = self._generator.get_memory_qubit_raw_template()
        memory_plaquettes = self._generator.get_memory_qubit_plaquettes(
            False,
            z_orientation.flip() if hadamard_transition else z_orientation,
            None,
            None,
        )
        memory_layer = PlaquetteLayer(memory_template, memory_plaquettes)

        if hadamard_transition:
            hadamard_template = self._generator.get_temporal_hadamard_raw_template()
            hadamard_plaquettes = self._generator.get_temporal_hadamard_plaquettes(
                False, z_orientation
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

    def _get_spatial_cube_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        x, y, z = spec.pipe_kind.x, spec.pipe_kind.y, spec.pipe_kind.z
        assert x is not None or y is not None
        spatial_boundary_basis: Basis = x if x is not None else y  # type: ignore
        # Get the plaquette indices mappings
        arms = FixedBoundaryPipeBuilder._get_spatial_cube_arms(spec)
        pipe_template = self._generator.get_spatial_cube_arm_raw_template(arms)

        def plaquettes_generator(is_reversed: bool, r: Basis | None, m: Basis | None) -> Plaquettes:
            return self._generator.get_spatial_cube_arm_plaquettes(
                spatial_boundary_basis, arms, spec.cube_specs, is_reversed, r, m
            )

        return _get_block(
            z,
            spec.has_spatial_up_or_down_pipe_in_timeslice,
            pipe_template,
            plaquettes_generator,
            block_temporal_height,
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

    def _get_spatial_regular_non_hadamard_pipe_plaquettes_factory(
        self, spec: PipeSpec
    ) -> Callable[[bool, Basis | None, Basis | None], Plaquettes]:
        if spec.pipe_kind.direction == Direction3D.X:
            # Pipe between two cubes aligned on the X axis
            z_observable_orientation = (
                Orientation.HORIZONTAL if spec.pipe_kind.y == Basis.X else Orientation.VERTICAL
            )
            return lambda is_reversed, r, m: (
                self._generator.get_memory_vertical_boundary_plaquettes(
                    is_reversed, z_observable_orientation, r, m
                )
            )
        # Else, pipe between two cubes aligned on the Y axis
        z_observable_orientation = (
            Orientation.HORIZONTAL if spec.pipe_kind.x == Basis.Z else Orientation.VERTICAL
        )
        return lambda is_reversed, r, m: (
            self._generator.get_memory_horizontal_boundary_plaquettes(
                is_reversed, z_observable_orientation, r, m
            )
        )

    def _get_spatial_regular_pipe_plaquettes_factory(
        self, spec: PipeSpec
    ) -> Callable[[bool, Basis | None, Basis | None], Plaquettes]:
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
            return lambda is_reversed, r, m: (
                self._generator.get_spatial_vertical_hadamard_plaquettes(
                    top_left_basis, is_reversed, r, m
                )
            )
        # Else, Hadamard pipe between two cubes aligned on the Y axis
        return lambda is_reversed, r, m: (
            self._generator.get_spatial_horizontal_hadamard_plaquettes(
                top_left_basis, is_reversed, r, m
            )
        )

    def _get_spatial_regular_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        assert all(not spec.is_spatial for spec in spec.cube_specs)
        plaquettes_factory = self._get_spatial_regular_pipe_plaquettes_factory(spec)
        template = self._get_spatial_regular_pipe_template(spec)
        z = spec.pipe_kind.get_basis_along(Direction3D.Z, at_head=False)
        assert z is not None, "Spatial pipe should have a basis in the Z direction."
        return _get_block(
            z,
            spec.has_spatial_up_or_down_pipe_in_timeslice,
            template,
            plaquettes_factory,
            block_temporal_height,
        )

    def get_spatial_pipe_block(
        self, spec: PipeSpec, block_temporal_height: LinearFunction
    ) -> Block:
        """Return a :class:`.Block` instance implementing the provided ``spec``."""
        assert spec.pipe_kind.is_spatial
        cube_specs = spec.cube_specs
        if cube_specs[0].is_spatial or cube_specs[1].is_spatial:
            return self._get_spatial_cube_pipe_block(spec, block_temporal_height)
        return self._get_spatial_regular_pipe_block(spec, block_temporal_height)


FIXED_BOUNDARY_CUBE_BUILDER = FixedBoundaryCubeBuilder(IdentityPlaquetteCompiler)
FIXED_BOUNDARY_PIPE_BUILDER = FixedBoundaryPipeBuilder(IdentityPlaquetteCompiler)
