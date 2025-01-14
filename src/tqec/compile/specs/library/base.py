from typing import Callable, Final

from tqec.compile.block import CompiledBlock
from tqec.compile.specs.base import (
    BlockBuilder,
    CubeSpec,
    PipeSpec,
    Substitution,
    SubstitutionBuilder,
)
from tqec.compile.specs.enums import JunctionArms
from tqec.computation.cube import Port, YCube, ZXCube
from tqec.enums import Basis
from tqec.exceptions import TQECException
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.plaquette import Plaquette, Plaquettes, RepeatedPlaquettes
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.translators.default import DefaultRPNGTranslator
from tqec.position import Direction3D
from tqec.scale import LinearFunction
from tqec.templates.enums import ZObservableOrientation
from tqec.templates.indices.base import RectangularTemplate
from tqec.templates.indices.enums import TemplateBorder
from tqec.templates.library.hadamard import (
    get_spatial_horizontal_hadamard_raw_template,
    get_spatial_horizontal_hadamard_rpng_descriptions,
    get_spatial_vertical_hadamard_raw_template,
    get_spatial_vertical_hadamard_rpng_descriptions,
    get_temporal_hadamard_rpng_descriptions,
)
from tqec.templates.library.memory import (
    get_memory_horizontal_boundary_raw_template,
    get_memory_horizontal_boundary_rpng_descriptions,
    get_memory_qubit_raw_template,
    get_memory_qubit_rpng_descriptions,
    get_memory_vertical_boundary_raw_template,
    get_memory_vertical_boundary_rpng_descriptions,
)
from tqec.templates.library.spatial import (
    get_spatial_junction_arm_raw_template,
    get_spatial_junction_arm_rpng_descriptions,
    get_spatial_junction_qubit_raw_template,
    get_spatial_junction_qubit_rpng_descriptions,
)


class BaseBlockBuilder(BlockBuilder):
    """Base implementation of the :class:`~tqec.compile.specs.base.BlockBuilder`
    interface.

    This class provides a default implementation that should be good enough for
    most of the block builders.
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

    def _get_plaquette(self, description: RPNGDescription) -> Plaquette:
        return self._compiler.compile(self._translator.translate(description))

    @staticmethod
    def _get_template_and_plaquettes(
        spec: CubeSpec,
    ) -> tuple[
        RectangularTemplate,
        tuple[
            FrozenDefaultDict[int, RPNGDescription],
            FrozenDefaultDict[int, RPNGDescription],
            FrozenDefaultDict[int, RPNGDescription],
        ],
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
        if not spec.is_spatial_junction:
            orientation = (
                ZObservableOrientation.HORIZONTAL
                if x == Basis.Z
                else ZObservableOrientation.VERTICAL
            )
            return get_memory_qubit_raw_template(), (
                get_memory_qubit_rpng_descriptions(orientation, z, None),
                get_memory_qubit_rpng_descriptions(orientation, None, None),
                get_memory_qubit_rpng_descriptions(orientation, None, z),
            )
        # else:
        return get_spatial_junction_qubit_raw_template(), (
            get_spatial_junction_qubit_rpng_descriptions(
                x, spec.junction_arms, z, None
            ),
            get_spatial_junction_qubit_rpng_descriptions(
                x, spec.junction_arms, None, None
            ),
            get_spatial_junction_qubit_rpng_descriptions(
                x, spec.junction_arms, None, z
            ),
        )

    def __call__(self, spec: CubeSpec) -> CompiledBlock:
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECException("Cannot build a block for a Port.")
        elif isinstance(kind, YCube):
            raise NotImplementedError("Y cube is not implemented.")
        # else
        template, (init, repeat, measure) = (
            BaseBlockBuilder._get_template_and_plaquettes(spec)
        )
        plaquettes = [
            Plaquettes(init.map_values(self._get_plaquette)),
            RepeatedPlaquettes(
                repeat.map_values(self._get_plaquette),
                repetitions=BaseBlockBuilder.DEFAULT_BLOCK_REPETITIONS,
            ),
            Plaquettes(measure.map_values(self._get_plaquette)),
        ]
        return CompiledBlock(template, plaquettes)


class BaseSubstitutionBuilder(SubstitutionBuilder):
    """Base implementation of the
    :class:`~tqec.compile.specs.base.SubstitutionBuilder` interface.

    This class provides a default implementation that should be good enough for
    most of the block builders.
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
            ZObservableOrientation.HORIZONTAL
            if spec.pipe_kind.x == Basis.Z
            else ZObservableOrientation.VERTICAL
        )
        memory_descriptions = get_memory_qubit_rpng_descriptions(
            z_observable_orientation
        )
        memory_plaquettes = Plaquettes(
            memory_descriptions.map_values(self._get_plaquette)
        )
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
        assert spec.pipe_kind.is_temporal
        assert spec.pipe_kind.has_hadamard

        #
        x_axis_basis_at_head = spec.pipe_kind.get_basis_along(
            Direction3D.X, at_head=True
        )
        assert (
            x_axis_basis_at_head is not None
        ), "A temporal pipe should have a non-None basis on the X-axis."

        first_layer_orientation: ZObservableOrientation
        second_layer_orientation: ZObservableOrientation
        if x_axis_basis_at_head == Basis.Z:
            first_layer_orientation = ZObservableOrientation.HORIZONTAL
            second_layer_orientation = ZObservableOrientation.VERTICAL
        else:
            first_layer_orientation = ZObservableOrientation.VERTICAL
            second_layer_orientation = ZObservableOrientation.HORIZONTAL
        hadamard_descriptions = get_temporal_hadamard_rpng_descriptions(
            first_layer_orientation
        )
        hadamard_plaquettes = Plaquettes(
            hadamard_descriptions.map_values(self._get_plaquette)
        )

        memory_descriptions = get_memory_qubit_rpng_descriptions(
            second_layer_orientation
        )
        memory_plaquettes = Plaquettes(
            memory_descriptions.map_values(self._get_plaquette)
        )
        return Substitution({-1: hadamard_plaquettes}, {0: memory_plaquettes})

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
    def _get_spatial_junction_arm(spec: PipeSpec) -> JunctionArms:
        """Returns the arm corresponding to the provided ``spec``.

        Args:
            spec: pipe specification to get the arm from.

        Raises:
            TQECException: if the provided ``spec`` is not a spatial pipe.
            TQECException: if the two blocks connected to the pipe are both
                spatial junctions, which is currently an unsupported case.

        Returns:
            the :class:`~tqec.compile.specs.enums.JunctionArms` instance
            corresponding to the provided ``spec``. The returned flag only
            contains one flag (i.e., it cannot be
            ``JunctionArms.RIGHT | JunctionArms.UP``).
        """
        assert spec.pipe_kind.is_spatial
        # Check that we do have a spatial junction.
        assert any(spec.is_spatial_junction for spec in spec.cube_specs)
        # For the moment, two spatial junctions side by side are not supported.
        if all(spec.is_spatial_junction for spec in spec.cube_specs):
            raise TQECException(
                "Found 2 spatial junctions connected. This is not supported yet."
            )
        spatial_junction_is_first: bool = spec.cube_specs[0].is_spatial_junction
        match spatial_junction_is_first, spec.pipe_kind.direction:
            case (True, Direction3D.X):
                return JunctionArms.RIGHT
            case (False, Direction3D.X):
                return JunctionArms.LEFT
            case (True, Direction3D.Y):
                return JunctionArms.UP
            case (False, Direction3D.Y):
                return JunctionArms.DOWN
            case _:
                raise TQECException(
                    "Should never happen as we are in a spatial (i.e., X/Y plane) junction."
                )

    def _get_spatial_junction_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        xbasis, ybasis = spec.pipe_kind.x, spec.pipe_kind.y
        assert xbasis is not None or ybasis is not None
        spatial_boundary_basis: Basis = xbasis if xbasis is not None else ybasis  # type: ignore
        # Get the plaquette indices mappings
        arm = BaseSubstitutionBuilder._get_spatial_junction_arm(spec)
        pipe_template = get_spatial_junction_arm_raw_template(arm)
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
            rpng_descriptions = get_spatial_junction_arm_rpng_descriptions(
                spatial_boundary_basis, arm, reset, measurement
            )
            plaquettes = rpng_descriptions.map_values(self._get_plaquette)
            src_substitution[layer_index] = Plaquettes(
                plaquettes.map_keys_if_present(mappings[0])
            )
            dst_substitution[layer_index] = Plaquettes(
                plaquettes.map_keys_if_present(mappings[1])
            )
        return Substitution(src_substitution, dst_substitution)

    @staticmethod
    def _get_spatial_regular_pipe_template(spec: PipeSpec) -> RectangularTemplate:
        """Returns the ``Template`` instance needed to implement the pipe
        representing the provided ``spec``."""
        assert spec.pipe_kind.is_spatial
        match spec.pipe_kind.direction, spec.pipe_kind.has_hadamard:
            case Direction3D.X, False:
                return get_memory_vertical_boundary_raw_template()
            case Direction3D.X, True:
                return get_spatial_vertical_hadamard_raw_template()
            case Direction3D.Y, False:
                return get_memory_horizontal_boundary_raw_template()
            case Direction3D.Y, True:
                return get_spatial_horizontal_hadamard_raw_template()
            case _:
                raise TQECException(
                    "Spatial pipes cannot have a direction equal to Direction3D.Z."
                )

    @staticmethod
    def _get_spatial_regular_pipe_descriptions_factory(
        spec: PipeSpec,
    ) -> Callable[
        [Basis | None, Basis | None], FrozenDefaultDict[int, RPNGDescription]
    ]:
        assert spec.pipe_kind.is_spatial
        match spec.pipe_kind.direction, spec.pipe_kind.has_hadamard:
            case Direction3D.X, False:
                # Non-Hadamard pipe in the X direction.
                z_observable_orientation = (
                    ZObservableOrientation.HORIZONTAL
                    if spec.pipe_kind.y == Basis.X
                    else ZObservableOrientation.VERTICAL
                )
                return lambda r, m: get_memory_vertical_boundary_rpng_descriptions(
                    z_observable_orientation, r, m
                )
            case Direction3D.X, True:
                # Hadamard pipe in the X direction.
                top_left_basis = spec.pipe_kind.get_basis_along(
                    Direction3D.Y, at_head=True
                )
                return lambda r, m: get_spatial_vertical_hadamard_rpng_descriptions(
                    top_left_basis == Basis.Z, r, m
                )
            case Direction3D.Y, False:
                # Non-Hadamard pipe in the Y direction.
                z_observable_orientation = (
                    ZObservableOrientation.HORIZONTAL
                    if spec.pipe_kind.x == Basis.Z
                    else ZObservableOrientation.VERTICAL
                )
                return lambda r, m: get_memory_horizontal_boundary_rpng_descriptions(
                    z_observable_orientation, r, m
                )

            case Direction3D.Y, True:
                # Hadamard pipe in the Y direction.
                top_left_basis = spec.pipe_kind.get_basis_along(
                    Direction3D.X, at_head=True
                )
                return lambda r, m: get_spatial_horizontal_hadamard_rpng_descriptions(
                    top_left_basis == Basis.Z, r, m
                )
            case _:
                raise TQECException(
                    "Spatial pipes cannot have a direction equal to Direction3D.Z."
                )

    def _get_spatial_regular_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        assert all(not spec.is_spatial_junction for spec in spec.cube_specs)
        description_factory = self._get_spatial_regular_pipe_descriptions_factory(spec)
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
            rpng_descriptions = description_factory(reset, measurement)
            plaquettes = rpng_descriptions.map_values(self._get_plaquette)
            src_substitution[layer_index] = Plaquettes(
                plaquettes.map_keys_if_present(mappings[0])
            )
            dst_substitution[layer_index] = Plaquettes(
                plaquettes.map_keys_if_present(mappings[1])
            )
        return Substitution(src_substitution, dst_substitution)

    def get_spatial_pipe_substitution(self, spec: PipeSpec) -> Substitution:
        assert spec.pipe_kind.is_spatial
        cube_specs = spec.cube_specs
        return (
            self._get_spatial_junction_pipe_substitution(spec)
            if cube_specs[0].is_spatial_junction or cube_specs[1].is_spatial_junction
            else self._get_spatial_regular_pipe_substitution(spec)
        )
