from __future__ import annotations

import inspect
from typing import Literal

from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.utils import PlaquetteMapper
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict


class FixedParityConventionGenerator:
    def __init__(self, translator: RPNGTranslator, compiler: PlaquetteCompiler):
        self._mapper = PlaquetteMapper(translator, compiler)

    def _not_implemented_exception(self) -> NotImplementedError:
        calling_method_name = inspect.stack(context=0)[1].function
        class_name = type(self).__name__
        return NotImplementedError(
            f"The method '{class_name}.{calling_method_name}' has not been "
            "implemented but is required to continue. Please implement it."
        )

    def get_bulk_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
        reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        raise self._not_implemented_exception()

    def get_3_body_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
        raise self._not_implemented_exception()

    def get_2_body_rpng_descriptions(
        self,
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        raise self._not_implemented_exception()

    ############################################################
    #                          Memory                          #
    ############################################################

    ########################################
    #             Regular qubit            #
    ########################################
    def get_memory_qubit_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a single logical qubit."""
        raise self._not_implemented_exception()

    def get_memory_qubit_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a
        standard memory operation on a logical qubit.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_qubit_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned logical qubit description.
            reset: basis of the reset operation performed on data-qubits.
                Defaults to ``None`` that translates to no reset being applied
                on data-qubits.
            measurement: basis of the measurement operation performed on
                data-qubits. Defaults to ``None`` that translates to no
                measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a standard
            memory operation on a logical qubit, optionally with resets or
            measurements on the data-qubits too.
        """
        raise self._not_implemented_exception()

    def get_memory_qubit_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Returns the plaquettes needed to implement a standard memory
        operation on a logical qubit.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_qubit_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned logical qubit description.
            reset: basis of the reset operation performed on data-qubits.
                Defaults to ``None`` that translates to no reset being applied
                on data-qubits.
            measurement: basis of the measurement operation performed on
                data-qubits. Defaults to ``None`` that translates to no
                measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a standard
            memory operation on a logical qubit, optionally with resets or
            measurements on the data-qubits too.
        """
        return self._mapper(self.get_memory_qubit_rpng_descriptions)(z_orientation, reset, measurement)

    ########################################
    #                X pipe                #
    ########################################
    def get_memory_vertical_boundary_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement a regular spatial pipe between two logical
        qubits aligned on the ``X`` axis."""
        raise self._not_implemented_exception()

    def get_memory_vertical_boundary_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a
        standard memory operation on a pipe between two neighbouring logical
        qubits aligned on the ``X``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_vertical_boundary_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned memory description.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a standard memory
            operation on a pipe between two neighbouring logical qubits aligned on
            the ``X``-axis, optionally with resets or measurements on the
            data-qubits too.
        """
        raise self._not_implemented_exception()

    def get_memory_vertical_boundary_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Returns the plaquettes needed to implement a standard memory
        operation on a pipe between two neighbouring logical qubits aligned on
        the ``X``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_vertical_boundary_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned memory description.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            the plaquettes needed to implement a standard memory operation on a
            pipe between two neighbouring logical qubits aligned on the
            ``X``-axis, optionally with resets or measurements on the
            data-qubits too.
        """
        return self._mapper(self.get_memory_vertical_boundary_rpng_descriptions)(z_orientation, reset, measurement)

    ########################################
    #                Y pipe                #
    ########################################
    def get_memory_horizontal_boundary_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a regular spatial pipe between two logical qubits
        aligned on the ``Y`` axis."""
        raise self._not_implemented_exception()

    def get_memory_horizontal_boundary_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a standard
        memory operation on a pipe between two neighbouring logical qubits aligned
        on the ``Y``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_horizontal_boundary_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned memory description.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a standard memory
            operation on a pipe between two neighbouring logical qubits aligned on
            the ``Y``-axis, optionally with resets or measurements on the
            data-qubits too.
        """
        raise self._not_implemented_exception()

    def get_memory_horizontal_boundary_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Returns the plaquettes needed to implement a standard memory
        operation on a pipe between two neighbouring logical qubits aligned on
        the ``Y``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_memory_horizontal_boundary_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable. Used to compute
                the stabilizers that should be measured on the boundaries and in
                the bulk of the returned memory description.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            the plaquettes needed to implement a standard memory operation on a
            pipe between two neighbouring logical qubits aligned on the
            ``Y``-axis, optionally with resets or measurements on the
            data-qubits too.
        """
        return self._mapper(self.get_memory_horizontal_boundary_rpng_descriptions)(z_orientation, reset, measurement)

    ############################################################
    #                          Spatial                         #
    ############################################################
    def get_spatial_cube_qubit_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.
        """
        raise self._not_implemented_exception()

    def get_spatial_cube_qubit_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a spatial
        cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC
            gadgets such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_spatial_cube_qubit_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            spatial_boundary_basis: stabilizers that are measured at each
                boundaries of the spatial cube.
            arms: flag-like enumeration listing the arms that are used around
                the logical qubit. The returned template will be adapted to be
                compatible with such a layout.
            reset: basis of the reset operation performed on data-qubits.
                Defaults to ``None`` that translates to no reset being applied
                on data-qubits.
            measurement: basis of the measurement operation performed on
                data-qubits. Defaults to ``None`` that translates to no
                measurement being applied on data-qubits.

        Raises:
            TQECException: if ``arms`` only contains 0 or 1 flag.
            TQECException: if ``arms`` describes an I-shaped junction (TOP/DOWN
                or LEFT/RIGHT).

        Returns:
            a description of the plaquettes needed to implement a spatial cube.
        """
        raise self._not_implemented_exception()

    def get_spatial_cube_qubit_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Returns the plaquettes needed to implement a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC
            gadgets such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_spatial_cube_qubit_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            spatial_boundary_basis: stabilizers that are measured at each
                boundaries of the spatial cube.
            arms: flag-like enumeration listing the arms that are used around
                the logical qubit. The returned template will be adapted to be
                compatible with such a layout.
            reset: basis of the reset operation performed on data-qubits.
                Defaults to ``None`` that translates to no reset being applied
                on data-qubits.
            measurement: basis of the measurement operation performed on
                data-qubits. Defaults to ``None`` that translates to no
                measurement being applied on data-qubits.

        Raises:
            TQECException: if ``arms`` only contains 0 or 1 flag.
            TQECException: if ``arms`` describes an I-shaped junction (TOP/DOWN
                or LEFT/RIGHT).

        Returns:
            the plaquettes needed to implement a spatial cube.
        """
        return self._mapper(self.get_spatial_cube_qubit_rpng_descriptions)(
            spatial_boundary_basis, arms, reset, measurement
        )

    ########################################
    #              Spatial arm             #
    ########################################
    def get_spatial_cube_arm_raw_template(self, arms: SpatialArms) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement the given spatial ``arms``.

        Args:
            arms: specification of the spatial arm(s) we want a template for.
                Needs to contain either one arm, or 2 arms that form a line
                (e.g., ``SpatialArms.UP | SpatialArms.DOWN``).
        """
        raise self._not_implemented_exception()

    def get_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement **one**
        pipe connecting to a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_spatial_cube_arm_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            spatial_boundary_basis: stabilizers that are measured at each
                boundaries of the spatial cube.
            arms: arm(s) of the spatial cube(s) linked by the pipe.
            linked_cubes: a tuple ``(u, v)`` where ``u`` and ``v`` are the
                specifications of the two ends of the pipe to generate RPNG
                descriptions for.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Raises:
            TQECException: if ``arm`` does not contain exactly 1 or 2 flags (i.e.,
                if it contains 0 or 3+ flags).

        Returns:
            a description of the plaquettes needed to implement **one** pipe
            connecting to a spatial cube.
        """
        raise self._not_implemented_exception()

    def get_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Returns the plaquettes needed to implement **one** pipe connecting to
        a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionPlaquetteGenerator.get_spatial_cube_arm_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            spatial_boundary_basis: stabilizers that are measured at each
                boundaries of the spatial cube.
            arms: arm(s) of the spatial cube(s) linked by the pipe.
            linked_cubes: a tuple ``(u, v)`` where ``u`` and ``v`` are the
                specifications of the two ends of the pipe to generate RPNG
                descriptions for.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Raises:
            TQECException: if ``arm`` does not contain exactly 1 or 2 flags (i.e.,
                if it contains 0 or 3+ flags).

        Returns:
            the plaquettes needed to implement **one** pipe connecting to a
            spatial cube.
        """
        return self._mapper(self.get_spatial_cube_arm_rpng_descriptions)(
            spatial_boundary_basis, arms, linked_cubes, reset, measurement
        )

    def _get_left_right_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        raise self._not_implemented_exception()

    def _get_up_down_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        raise self._not_implemented_exception()

    ############################################################
    #                         Hadamard                         #
    ############################################################

    ########################################
    #           Regular junction           #
    ########################################
    def get_temporal_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.Template` instance
        needed to implement a transversal Hadamard gate applied on one logical
        qubit."""
        raise self._not_implemented_exception()

    def get_temporal_hadamard_rpng_descriptions(
        self, z_orientation: Orientation = Orientation.HORIZONTAL
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a transversal
        Hadamard gate applied on one logical qubit.

        Warning:
            This method is tightly coupled with
            :meth:`PlaquetteGenerator.get_temporal_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this
            method.

        Arguments:
            z_orientation: orientation of the ``Z`` observable at the beginning
                of the generated circuit description. The ``Z`` observable
                orientation will be flipped at the end of the returned circuit
                description, which is exactly the expected behaviour for a
                Hadamard transition.
                Used to compute the stabilizers that should be measured on the
                boundaries and in the bulk of the returned logical qubit
                description.

        Returns:
            a description of the plaquettes needed to implement a transversal
            Hadamard gate applied on one logical qubit.
        """
        raise self._not_implemented_exception()

    def get_temporal_hadamard_plaquettes(self, z_orientation: Orientation = Orientation.HORIZONTAL) -> Plaquettes:
        return self._mapper(self.get_temporal_hadamard_rpng_descriptions)(z_orientation)

    ########################################
    #                X pipe                #
    ########################################
    def get_spatial_vertical_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.Template` instance needed to
        implement a spatial Hadamard pipe between two logical qubits aligned on
        the ``X`` axis."""
        raise self._not_implemented_exception()

    def get_spatial_vertical_hadamard_rpng_descriptions(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a Hadamard
        spatial transition between two neighbouring logical qubits aligned on the
        ``X`` axis.

        The Hadamard transition basically exchanges the ``X`` and ``Z`` logical
        observables between two neighbouring logical qubits aligned on the ``X``
        axis.

        Note:
            By convention, the hadamard-like transition is performed at the
            top-most plaquettes.

        Warning:
            This method is tightly coupled with
            :meth:`PlaquetteGenerator.get_spatial_vertical_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this
            method.

        Arguments:
            top_left_is_z_stabilizer: if ``True``, the plaquette with index 5 in
                :class:`~tqec.templates.qubit.QubitVerticalBorders`
                should be measuring a ``Z`` stabilizer on its 2 left-most
                data-qubits and a ``X`` stabilizer on its 2 right-most
                data-qubits. Else, it measures a ``X`` stabilizer on its two
                left-most data-qubits and a ``Z`` stabilizer on its two
                right-most data-qubits.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a Hadamard
            spatial transition between two neighbouring logical qubits aligned
            on the ``X`` axis.
        """
        raise self._not_implemented_exception()

    def get_spatial_vertical_hadamard_plaquettes(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        return self._mapper(self.get_spatial_vertical_hadamard_rpng_descriptions)(
            top_left_is_z_stabilizer, reset, measurement
        )

    ########################################
    #                Y pipe                #
    ########################################
    def get_spatial_horizontal_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.Template` instance needed to
        implement a spatial Hadamard pipe between two neighbouring logical
        qubits aligned on the ``Y`` axis."""
        raise self._not_implemented_exception()

    def get_spatial_horizontal_hadamard_rpng_descriptions(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a Hadamard
        spatial transition between two neighbouring logical qubits aligned on the
        ``Y`` axis.

        The Hadamard transition basically exchanges the ``X`` and ``Z`` logical
        observables between two neighbouring logical qubits aligned on the ``Y``
        axis.

        Note:
            By convention, the hadamard-like transition is performed at the
            top-most plaquettes.

        Warning:
            This method is tightly coupled with
            :meth:`PlaquetteGenerator.get_spatial_horizontal_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this
            method.

        Arguments:
            top_left_is_z_stabilizer: if ``True``, the plaquette with index 5 in
                :class:`~tqec.templates.qubit.QubitHorizontalBorders` should be
                measuring a ``Z`` stabilizer on its 2 top-most data-qubits and a
                ``X`` stabilizer on its 2 bottom-most data-qubits. Else, it
                measures a ``X`` stabilizer on its two top-most data-qubits and
                a ``Z`` stabilizer on its two bottom-most data-qubits.
            reset: basis of the reset operation performed on **internal**
                data-qubits. Defaults to ``None`` that translates to no reset
                being applied on data-qubits.
            measurement: basis of the measurement operation performed on
                **internal** data-qubits. Defaults to ``None`` that translates
                to no measurement being applied on data-qubits.

        Returns:
            a description of the plaquettes needed to implement a Hadamard
            spatial transition between two neighbouring logical qubits aligned
            on the ``Y`` axis.
        """
        raise self._not_implemented_exception()

    def get_spatial_horizontal_hadamard_plaquettes(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        return self._mapper(self.get_spatial_horizontal_hadamard_rpng_descriptions)(
            top_left_is_z_stabilizer, reset, measurement
        )
