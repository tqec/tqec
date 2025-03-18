from typing import Callable, Final

from tqec.compile.block import CompiledBlock
from tqec.compile.specs.base import (
    BlockBuilder,
    CubeSpec,
    PipeSpec,
    Substitution,
    SubstitutionBuilder,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators import (
    get_memory_horizontal_boundary_plaquettes,
    get_memory_horizontal_boundary_raw_template,
    get_memory_qubit_plaquettes,
    get_memory_qubit_raw_template,
    get_memory_vertical_boundary_plaquettes,
    get_memory_vertical_boundary_raw_template,
    get_spatial_cube_arm_plaquettes,
    get_spatial_cube_arm_raw_template,
    get_spatial_cube_qubit_plaquettes,
    get_spatial_cube_qubit_raw_template,
)
from tqec.computation.cube import Port, YHalfCube, ZXCube
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquette, Plaquettes, RepeatedPlaquettes
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.templates.enums import TemplateBorder
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D
from tqec.utils.scale import LinearFunction


class BaseBlockBuilder(BlockBuilder):
    """Base implementation of the :class:`~tqec.compile.specs.base.BlockBuilder`
    interface.

    This class provides a good enough default implementation that should be
    enough for most of the block builders.
    """

    DEFAULT_BLOCK_REPETITIONS: Final[LinearFunction] = LinearFunction(2, -1)

    def __init__(self, compiler: PlaquetteCompiler) -> None:
        """Initialise the :class:`BaseBlockBuilder` with a compiler.

        Args:
            compiler: compiler to transform the plaquettes in the standard
                implementation to a custom implementation.
        """
        self._translator = DefaultRPNGTranslator()
        self._compiler = compiler

    @staticmethod
    def _get_template_and_plaquettes(
        spec: CubeSpec,
    ) -> tuple[
        RectangularTemplate,
        tuple[Plaquettes, Plaquettes, Plaquettes],
    ]:
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
            return get_memory_qubit_raw_template(), (
                get_memory_qubit_plaquettes(orientation, z, None),
                get_memory_qubit_plaquettes(orientation, None, None),
                get_memory_qubit_plaquettes(orientation, None, z),
            )
        # else:
        return get_spatial_cube_qubit_raw_template(), (
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, z, None),
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, None),
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, z),
        )

    def __call__(self, spec: CubeSpec) -> CompiledBlock:
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECException("Cannot build a block for a Port.")
        elif isinstance(kind, YHalfCube):
            raise NotImplementedError("Y cube is not implemented.")
        # else
        template, (init, repeat, measure) = (
            BaseBlockBuilder._get_template_and_plaquettes(spec)
        )
        plaquettes = [
            init,
            RepeatedPlaquettes(
                repeat.collection,
                repetitions=BaseBlockBuilder.DEFAULT_BLOCK_REPETITIONS,
            ),
            measure,
        ]
        return CompiledBlock(template, plaquettes)


class BaseSubstitutionBuilder(SubstitutionBuilder):
    """Base implementation of the
    :class:`~tqec.compile.specs.base.SubstitutionBuilder` interface.

    This class provides a good enough default implementation that should be
    enough for most of the block builders.
    """

    def __init__(self, compiler: PlaquetteCompiler) -> None:
        """Initialise the :class:`BaseSubstitutionBuilder` with a compiler.

        Args:
            compiler: compiler to transform the plaquettes in the standard
                implementation to a custom implementation.
        """
        self._translator = DefaultRPNGTranslator()
        self._compiler = compiler

    def _get_plaquette(self, description: RPNGDescription) -> Plaquette:
        return self._compiler.compile(self._translator.translate(description))

    def __call__(self, spec: PipeSpec) -> Substitution:
        if spec.pipe_kind.is_temporal:
            return self.get_temporal_pipe_substitution(spec)
        return self.get_spatial_pipe_substitution(spec)

    ##############################
    #    TEMPORAL SUBSTITUTION   #
    ##############################

    def get_temporal_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        """Returns the substitution that should be performed to implement the
        provided ``spec``.

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a temporal pipe.

        Raises:
            AssertionError: if ``spec`` does not represent a temporal junction.

        Returns:
            the substitution that should be performed to implement the provided
            ``spec``.
        """
        assert spec.pipe_kind.is_temporal
        if spec.pipe_kind.has_hadamard:
            return self._get_temporal_hadamard_pipe_substitution(spec)
        # Else, it is a regular temporal junction
        return self._get_temporal_non_hadamard_pipe_substitution(spec)

    def _get_temporal_non_hadamard_pipe_substitution(
        self, spec: PipeSpec
    ) -> Substitution:
        """Returns the substitution that should be performed to implement a
        regular temporal junction without Hadamard transition.

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a regular (i.e., non-Hadamard) temporal pipe.

        Raises:
            AssertionError: if the provided ``pipe`` is not a temporal pipe, or
                if it contains a Hadamard transition.

        Returns:
            the substitution that should be performed to implement the provided
            ``spec``.
        """
        assert spec.pipe_kind.is_temporal
        assert not spec.pipe_kind.has_hadamard

        z_observable_orientation = (
            Orientation.HORIZONTAL
            if spec.pipe_kind.x == Basis.Z
            else Orientation.VERTICAL
        )
        memory_plaquettes = get_memory_qubit_plaquettes(z_observable_orientation)
        return Substitution({-1: memory_plaquettes}, {0: memory_plaquettes})

    def _get_temporal_hadamard_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        """Returns the substitution that should be performed to implement a
        Hadamard temporal junction.

        Note:
            This method performs the Hadamard transition at the end of the
            layer that appear first (i.e., temporally before the other, or in
            other words the one with a lower Z index).

        Args:
            spec: description of the pipe that should be implemented by this
                method. Should be a Hadamard temporal pipe.

        Raises:
            AssertionError: if the provided ``pipe`` is not a temporal pipe, or
                if it is not a Hadamard transition.

        Returns:
            the substitution that should be performed to implement the provided
            ``spec``.
        """
        raise NotImplementedError("Hamadard pipes are not implemented.")

    ##############################
    #    SPATIAL SUBSTITUTION    #
    ##############################

    @staticmethod
    def _get_plaquette_indices_mapping(
        qubit_templates: tuple[RectangularTemplate, RectangularTemplate],
        pipe_template: RectangularTemplate,
        direction: Direction3D,
    ) -> tuple[dict[int, int], dict[int, int]]:
        """Returns the plaquette indices mappings from ``pipe_template`` to the
        two provided ``qubit_templates``.

        This static method is re-used in different methods of this class to
        build the mappings from plaquette indices on each borders of the provided
        ``pipe_template`` to the plaquette indices on the respective border of
        both of the provided ``qubit_templates``.

        ``qubit_templates`` is supposed to be "sorted": the first template
        should come "first" (i.e., be associated to the block with the minimum
        coordinate in the provided ``direction``).

        Args:
            qubit_templates: templates used by the two blocks that are connected
                by the pipe. Should be "sorted" (i.e., if
                ``direction == Direction3D.X`` then ``qubit_template[0]`` is the
                block on the left of the pipe and ``qubit_templates[1]`` is the
                block on the right).
            pipe_template: template used to build the pipe.
            direction: direction of the pipe. This is used to determine which
                side of the different templates should be matched together.

        Raises:
            TQECException: if ``direction == Direction3D.Z``.

        Returns:
            two mappings, the first one for plaquette indices from
            ``pipe_template`` to ``qubit_templates[0]`` and the second one from
            ``pipe_template`` to ``qubit_templates[1]``.
        """
        tb1: TemplateBorder
        tb2: TemplateBorder
        match direction:
            case Direction3D.X:
                tb1 = TemplateBorder.LEFT
                tb2 = TemplateBorder.RIGHT
            case Direction3D.Y:
                tb1 = TemplateBorder.TOP
                tb2 = TemplateBorder.BOTTOM
            case Direction3D.Z:
                raise TQECException("This method cannot be used with a temporal pipe.")

        return (
            pipe_template.get_border_indices(tb1).to(
                qubit_templates[0].get_border_indices(tb2)
            ),
            pipe_template.get_border_indices(tb2).to(
                qubit_templates[1].get_border_indices(tb1)
            ),
        )

    @staticmethod
    def _get_spatial_cube_arm(spec: PipeSpec) -> SpatialArms:
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

    def _get_spatial_cube_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        xbasis, ybasis = spec.pipe_kind.x, spec.pipe_kind.y
        assert xbasis is not None or ybasis is not None
        spatial_boundary_basis: Basis = xbasis if xbasis is not None else ybasis  # type: ignore
        # Get the plaquette indices mappings
        arms = BaseSubstitutionBuilder._get_spatial_cube_arm(spec)
        pipe_template = get_spatial_cube_arm_raw_template(arms)
        mappings = BaseSubstitutionBuilder._get_plaquette_indices_mapping(
            spec.cube_templates, pipe_template, spec.pipe_kind.direction
        )
        # The end goal of this function is to fill in the following 2 variables
        # and use them to make a Substitution instance.
        src_substitution: dict[int, Plaquettes] = {}
        dst_substitution: dict[int, Plaquettes] = {}
        for layer_index, (reset, measurement) in enumerate(
            [(spec.pipe_kind.z, None), (None, None), (None, spec.pipe_kind.z)]
        ):
            plaquettes = get_spatial_cube_arm_plaquettes(
                spatial_boundary_basis, arms, reset, measurement
            )
            src_substitution[layer_index] = Plaquettes(
                plaquettes.collection.map_keys_if_present(mappings[0])
            )
            dst_substitution[layer_index] = Plaquettes(
                plaquettes.collection.map_keys_if_present(mappings[1])
            )
        return Substitution(src_substitution, dst_substitution)

    @staticmethod
    def _get_spatial_regular_pipe_template(spec: PipeSpec) -> RectangularTemplate:
        """Returns the ``Template`` instance needed to implement the pipe
        representing the provided ``spec``."""
        assert spec.pipe_kind.is_spatial
        if spec.pipe_kind.has_hadamard:
            raise NotImplementedError("Hadamard pipes are not implemented.")
        match spec.pipe_kind.direction:
            case Direction3D.X:
                return get_memory_vertical_boundary_raw_template()
            case Direction3D.Y:
                return get_memory_horizontal_boundary_raw_template()
            case _:
                raise TQECException(
                    "Spatial pipes cannot have a direction equal to Direction3D.Z."
                )

    @staticmethod
    def _get_spatial_regular_pipe_plaquettes_factory(
        spec: PipeSpec,
    ) -> Callable[[Basis | None, Basis | None], Plaquettes]:
        assert spec.pipe_kind.is_spatial
        if spec.pipe_kind.has_hadamard:
            raise NotImplementedError("Hadamard pipes are not implemented.")
        match spec.pipe_kind.direction:
            case Direction3D.X:
                # Non-Hadamard pipe in the X direction.
                z_observable_orientation = (
                    Orientation.HORIZONTAL
                    if spec.pipe_kind.y == Basis.X
                    else Orientation.VERTICAL
                )
                return lambda r, m: get_memory_vertical_boundary_plaquettes(
                    z_observable_orientation, r, m
                )
            case Direction3D.Y:
                # Non-Hadamard pipe in the Y direction.
                z_observable_orientation = (
                    Orientation.HORIZONTAL
                    if spec.pipe_kind.x == Basis.Z
                    else Orientation.VERTICAL
                )
                return lambda r, m: get_memory_horizontal_boundary_plaquettes(
                    z_observable_orientation, r, m
                )
            case _:
                raise TQECException(
                    "Spatial pipes cannot have a direction equal to Direction3D.Z."
                )

    def _get_spatial_regular_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        assert all(not spec.is_spatial for spec in spec.cube_specs)
        plaquettes_factory = self._get_spatial_regular_pipe_plaquettes_factory(spec)
        template = self._get_spatial_regular_pipe_template(spec)
        mappings = BaseSubstitutionBuilder._get_plaquette_indices_mapping(
            spec.cube_templates, template, spec.pipe_kind.direction
        )

        # The end goal of this function is to fill in the following 2 variables
        # and use them to make a Substitution instance.
        src_substitution: dict[int, Plaquettes] = {}
        dst_substitution: dict[int, Plaquettes] = {}
        for layer_index, (reset, measurement) in enumerate(
            [(spec.pipe_kind.z, None), (None, None), (None, spec.pipe_kind.z)]
        ):
            plaquettes = plaquettes_factory(reset, measurement)
            src_substitution[layer_index] = Plaquettes(
                plaquettes.collection.map_keys_if_present(mappings[0])
            )
            dst_substitution[layer_index] = Plaquettes(
                plaquettes.collection.map_keys_if_present(mappings[1])
            )
        return Substitution(src_substitution, dst_substitution)

    def get_spatial_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        assert spec.pipe_kind.is_spatial
        cube_specs = spec.cube_specs
        return (
            self._get_spatial_cube_pipe_substitution(spec)
            if cube_specs[0].is_spatial or cube_specs[1].is_spatial
            else self._get_spatial_regular_pipe_substitution(spec)
        )
