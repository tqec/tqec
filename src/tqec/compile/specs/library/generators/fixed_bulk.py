from __future__ import annotations

import inspect
from typing import Literal

import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.utils import PlaquetteMapper
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.debug import DrawPolygon, PlaquetteDebugInformation
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def make_fixed_bulk_realignment_plaquette(
    stabilizer_basis: Basis,
    z_orientation: Orientation,
    mq_reset: Basis,
    mq_measurement: Basis,
    debug_basis: PauliBasis | None = None,
) -> Plaquette:
    """Make the plaquette used for fixed-bulk temporal Hadamard transition."""
    qubits = SquarePlaquetteQubits()
    cx_targets: list[tuple[int, int]]
    # used to match the 5-timestep schedule in the other part of computation
    cx_schedule: list[int]
    match stabilizer_basis, z_orientation:
        case Basis.Z, Orientation.VERTICAL:
            cx_targets = [(0, 4), (1, 4), (4, 2), (4, 0)]
            cx_schedule = [1, 2, 3, 5]
        case Basis.Z, Orientation.HORIZONTAL:
            cx_targets = [(0, 4), (2, 4), (4, 1), (4, 0)]
            cx_schedule = [1, 3, 4, 5]
        case Basis.X, Orientation.VERTICAL:
            cx_targets = [(4, 0), (4, 2), (1, 4), (0, 4)]
            cx_schedule = [1, 3, 4, 5]
        case Basis.X, Orientation.HORIZONTAL:
            cx_targets = [(4, 0), (4, 1), (2, 4), (0, 4)]
            cx_schedule = [1, 2, 3, 5]
    circuit = stim.Circuit()
    circuit.append(f"R{mq_reset.value}", qubits.syndrome_qubits_indices, [])
    circuit.append("TICK", [], [])
    for targets in cx_targets:
        circuit.append("CX", targets, [])
        circuit.append("TICK", [], [])
    circuit.append(f"M{mq_measurement.value}", qubits.syndrome_qubits_indices, [])
    circuit.append("H", qubits.data_qubits_indices, [])
    schedule = [0, *cx_schedule, 6]
    scheduled_circuit = ScheduledCircuit.from_circuit(circuit, schedule, qubits.qubit_map)
    return Plaquette(
        f"fixed_bulk_realignment_{stabilizer_basis}_{z_orientation.value}_R{mq_reset}_M{mq_measurement}",
        qubits,
        scheduled_circuit,
        mergeable_instructions=frozenset({"H"}),
        debug_information=PlaquetteDebugInformation(
            draw_polygons=(DrawPolygon(debug_basis) if debug_basis is not None else None)
        ),
    )


class FixedBulkConventionGenerator:
    def __init__(self, translator: RPNGTranslator, compiler: PlaquetteCompiler):
        """Contain the plaquette generation procedures to implement the fixed bulk convention.

        Args:
            translator: instance used to translate :class:`.RPNGDescription` instances into
                :class:`.Plaquette` instances.
            compiler: instance used to transform :class:`.Plaquette` instances into other
                :class:`.Plaquette` instances.

        """
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
        """Get plaquettes that are supposed to be used in the bulk.

        This function returns the four 4-body stabilizer measurement plaquettes
        containing 5 rounds that can be arbitrarily tiled without any gate schedule
        clash. These plaquettes are organised by basis and hook orientation.

        Args:
            reset: basis of the reset operation performed on data-qubits. Defaults
                to ``None`` that translates to no reset being applied on data-qubits.
            measurement: basis of the measurement operation performed on data-qubits.
                Defaults to ``None`` that translates to no measurement being applied
                on data-qubits.
            reset_and_measured_indices: data-qubit indices that should be impacted
                by the provided ``reset`` and ``measurement`` values.

        Returns:
            a mapping with 4 plaquettes: one for each basis (either ``X`` or ``Z``)
            and for each hook orientation (either ``HORIZONTAL`` or ``VERTICAL``).

        """
        # _r/_m: reset/measurement basis applied to each data-qubit in
        # reset_and_measured_indices
        _r = reset.value.lower() if reset is not None else "-"
        _m = measurement.value.lower() if measurement is not None else "-"
        # rs/ms: resets/measurements basis applied for each data-qubit
        rs = [_r if i in reset_and_measured_indices else "-" for i in range(4)]
        ms = [_m if i in reset_and_measured_indices else "-" for i in range(4)]
        # 2-qubit gate schedules
        vsched, hsched = (1, 4, 3, 5), (1, 2, 3, 5)
        return {
            Basis.X: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, vsched, ms))
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"{r}x{s}{m}" for r, s, m in zip(rs, hsched, ms))
                ),
            },
            Basis.Z: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, vsched, ms))
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"{r}z{s}{m}" for r, s, m in zip(rs, hsched, ms))
                ),
            },
        }

    def get_3_body_rpng_descriptions(
        self,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
        """Return the four 3-body stabilizer measurement plaquettes.

        Args:
            reset: basis of the reset operation performed on data-qubits. Defaults
                to ``None`` that translates to no reset being applied on data-qubits.
            measurement: basis of the measurement operation performed on data-qubits.
                Defaults to ``None`` that translates to no measurement being applied
                on data-qubits.

        Returns:
            the four 3-body stabilizer measurement plaquettes. Their order follow the usual
            convention: ``(top_left, top_right, bottom_left, bottom_right)``.

        """
        # r/m: reset/measurement basis applied to each data-qubit
        r = reset.value.lower() if reset is not None else "-"
        m = measurement.value.lower() if measurement is not None else "-"
        # Note: the schedule of CNOT gates in corner plaquettes is less important
        # because hook errors do not exist on 3-body stabilizers. We arbitrarily
        # chose the schedule of the plaquette group the corner belongs to.
        # Note that we include resets and measurements on all the used data-qubits.
        # That should be fine because this plaquette only touches cubes and pipes
        # that are related to the spatial junction being implemented, and it is not
        # valid to have a temporal pipe coming from below a spatial junction, hence
        # the data-qubits cannot be already initialised to a value we would like to
        # keep and that would be destroyed by reset/measurement.
        return (
            RPNGDescription.from_string(f"---- {r}z4{m} {r}z3{m} {r}z5{m}"),
            RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} {r}x5{m}"),
            RPNGDescription.from_string(f"{r}x1{m} {r}x2{m} ---- {r}x5{m}"),
            RPNGDescription.from_string(f"{r}z1{m} {r}z4{m} {r}z3{m} ----"),
        )

    def get_2_body_rpng_descriptions(
        self,
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        """Get plaquettes that are supposed to be used on the boundaries.

        This function returns the eight 2-body stabilizer measurement plaquettes
        that can be used on the 5-round plaquettes returned by
        :meth:`get_bulk_plaquettes`.

        Note:
            The 2-body stabilizer measurement plaquettes returned by this function
            all follow the same schedule: ``1-2-3-5``.

        Warning:
            By convention, the 2-body stabilizers never reset/measure any
            data-qubit. This is done because it is way simpler to reset the correct
            data-qubits in 4-body stabilizers, and the resets/measurements in 2-body
            stabilizers would be redundant.

        Warning:
            This function uses the :class:`~tqec.plaquette.enums.PlaquetteOrientation`
            class. For a 2-body stabilizer measurement plaquette, the "orientation"
            corresponds to the direction in which the rounded side is pointing.
            So a plaquette with the orientation ``PlaquetteOrientation.DOWN`` has the
            following properties:
            - it measures the 2 data-qubits on the **top** side of the usual 4-body
            stabilizer measurement plaquette,
            - it can be used for a bottom boundary,
            - its rounded side points downwards.

        Returns:
            a mapping with 8 plaquettes: one for each basis (either ``X`` or ``Z``)
            and for each plaquette orientation (``UP``, ``DOWN``, ``LEFT`` or
            ``RIGHT``).

        """
        return {
            Basis.X: {
                PlaquetteOrientation.DOWN: RPNGDescription.from_string("-x1- -x2- ---- ----"),
                PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -x2- ---- -x5-"),
                PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -x3- -x5-"),
                PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-x1- ---- -x3- ----"),
            },
            Basis.Z: {
                PlaquetteOrientation.DOWN: RPNGDescription.from_string("-z1- -z2- ---- ----"),
                PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -z2- ---- -z5-"),
                PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -z3- -z5-"),
                PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-z1- ---- -z3- ----"),
            },
        }

    ############################################################
    #                          Memory                          #
    ############################################################

    ########################################
    #             Regular qubit            #
    ########################################
    def get_memory_qubit_raw_template(self) -> RectangularTemplate:
        """Return the template instance needed to implement a single logical qubit."""
        return QubitTemplate()

    def get_memory_qubit_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a standard memory operation
        on a logical qubit.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_qubit_raw_template`
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
        # Border plaquette indices
        up, down, left, right = (
            (6, 13, 7, 12) if z_orientation == Orientation.VERTICAL else (5, 14, 8, 11)
        )
        # Basis for top/bottom and left/right boundary plaquettes
        hbasis = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        vbasis = hbasis.flipped()
        # Hook errors orientations
        zhook = z_orientation.flip()
        xhook = zhook.flip()
        # Get plaquette descriptions we will need later
        bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement)
        two_body_descriptions = self.get_2_body_rpng_descriptions()
        return FrozenDefaultDict(
            {
                up: two_body_descriptions[vbasis][PlaquetteOrientation.UP],
                left: two_body_descriptions[hbasis][PlaquetteOrientation.LEFT],
                # Bulk
                9: bulk_descriptions[Basis.Z][zhook],
                10: bulk_descriptions[Basis.X][xhook],
                right: two_body_descriptions[hbasis][PlaquetteOrientation.RIGHT],
                down: two_body_descriptions[vbasis][PlaquetteOrientation.DOWN],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_memory_qubit_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a standard memory operation on a logical
        qubit.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_qubit_raw_template`
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
        return self._mapper(self.get_memory_qubit_rpng_descriptions)(
            z_orientation, reset, measurement
        )

    ########################################
    #                X pipe                #
    ########################################
    def get_memory_vertical_boundary_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.RectangularTemplate` instance needed to
        implement a regular spatial pipe between two logical qubits aligned on the ``X`` axis.
        """
        return QubitVerticalBorders()

    def get_memory_vertical_boundary_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a standard memory operation
        on a pipe between two neighbouring logical qubits aligned on the ``X``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_vertical_boundary_raw_template`
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
        # Border plaquette indices
        up, down = (2, 3) if z_orientation == Orientation.VERTICAL else (1, 4)
        # Basis for top/bottom boundary plaquettes
        vbasis = Basis.Z if z_orientation == Orientation.VERTICAL else Basis.X
        # Hook errors orientations
        zhook = z_orientation.flip()
        xhook = zhook.flip()
        # Generating the plaquette descriptions we will need later
        left_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (1, 3))
        right_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (0, 2))
        two_body_descriptions = self.get_2_body_rpng_descriptions()

        return FrozenDefaultDict(
            {
                up: two_body_descriptions[vbasis][PlaquetteOrientation.UP],
                down: two_body_descriptions[vbasis][PlaquetteOrientation.DOWN],
                # LEFT bulk
                5: left_bulk_descriptions[Basis.Z][zhook],
                6: left_bulk_descriptions[Basis.X][xhook],
                # RIGHT bulk
                7: right_bulk_descriptions[Basis.X][xhook],
                8: right_bulk_descriptions[Basis.Z][zhook],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_memory_vertical_boundary_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a standard memory operation on a pipe between
        two neighbouring logical qubits aligned on the ``X``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_vertical_boundary_raw_template`
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
        return self._mapper(self.get_memory_vertical_boundary_rpng_descriptions)(
            z_orientation, reset, measurement
        )

    ########################################
    #                Y pipe                #
    ########################################
    def get_memory_horizontal_boundary_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.RectangularTemplate` instance needed to
        implement a regular spatial pipe between two logical qubits aligned on the ``Y`` axis.
        """
        return QubitHorizontalBorders()

    def get_memory_horizontal_boundary_rpng_descriptions(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a standard memory operation
        on a pipe between two neighbouring logical qubits aligned on the ``Y``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_horizontal_boundary_raw_template`
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
        # Border plaquette indices
        left, right = (1, 4) if z_orientation == Orientation.VERTICAL else (3, 2)
        # Basis for left/right boundary plaquettes
        hbasis = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        # Hook errors orientations
        zhook = z_orientation.flip()
        xhook = zhook.flip()
        # Generating the plaquette descriptions we will need later
        up_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (2, 3))
        down_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (0, 1))
        two_body_descriptions = self.get_2_body_rpng_descriptions()

        return FrozenDefaultDict(
            {
                left: two_body_descriptions[hbasis][PlaquetteOrientation.LEFT],
                right: two_body_descriptions[hbasis][PlaquetteOrientation.RIGHT],
                # TOP bulk
                5: up_bulk_descriptions[Basis.Z][zhook],
                6: up_bulk_descriptions[Basis.X][xhook],
                # BOTTOM bulk
                7: down_bulk_descriptions[Basis.X][xhook],
                8: down_bulk_descriptions[Basis.Z][zhook],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_memory_horizontal_boundary_plaquettes(
        self,
        z_orientation: Orientation = Orientation.HORIZONTAL,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a standard memory operation on a pipe between
        two neighbouring logical qubits aligned on the ``Y``-axis.

        Note:
            if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
            measurement) operation in the provided basis will be inserted **only
            on internal data-qubits**. Here, internal data-qubits are all the
            qubits that are in the middle of the template.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_memory_horizontal_boundary_raw_template`
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
        return self._mapper(self.get_memory_horizontal_boundary_rpng_descriptions)(
            z_orientation, reset, measurement
        )

    ############################################################
    #                          Spatial                         #
    ############################################################
    def get_spatial_cube_qubit_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.RectangularTemplate` instance needed to
        implement a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.

        """
        return QubitSpatialCubeTemplate()

    def get_spatial_cube_qubit_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC
            gadgets such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_spatial_cube_qubit_raw_template`
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
            TQECError: if ``arms`` only contains 0 or 1 flag.
            TQECError: if ``arms`` describes an I-shaped junction (TOP/DOWN
                or LEFT/RIGHT).

        Returns:
            a description of the plaquettes needed to implement a spatial cube.

        """
        # In this function implementation, all the indices used are referring to the
        # indices returned by the QubitSpatialCubeTemplate template. They are
        # copied below for convenience, but the only source of truth is in the
        # QubitSpatialCubeTemplate docstring!
        #      1   9  10   9  10   9  10   9  10   2
        #     11   5  17  13  17  13  17  13   6  21
        #     12  20  13  17  13  17  13  17  14  22
        #     11  16  20  13  17  13  17  14  18  21
        #     12  20  16  20  13  17  14  18  14  22
        #     11  16  20  16  19  15  18  14  18  21
        #     12  20  16  19  15  19  15  18  14  22
        #     11  16  19  15  19  15  19  15  18  21
        #     12   7  15  19  15  19  15  19   8  22
        #      3  23  24  23  24  23  24  23  24   4
        if arms in SpatialArms.I_shaped_arms():
            raise TQECError(
                "I-shaped spatial junctions (i.e., spatial junctions with only two "
                "arms that are the opposite of each other: LEFT/RIGHT or UP/DOWN) "
                "should not use get_spatial_cube_qubit_template but rather use "
                "a conventional memory logical qubit with get_memory_qubit_template."
            )
        # Get parity information in a more convenient format.
        boundary_is_z = spatial_boundary_basis == Basis.Z
        # Pre-define some collection of plaquette descriptions
        corner_descriptions = self.get_3_body_rpng_descriptions(reset, measurement)
        bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement)
        two_body_descriptions = self.get_2_body_rpng_descriptions()

        mapping: dict[int, RPNGDescription] = {}

        ####################
        #    Boundaries    #
        ####################
        # Fill the boundaries that should be filled in the returned template
        # because they have no arms, and so will not be filled later.
        # Note that indices 1, 2, 3 and 4 **might** be set twice in the 4 ifs
        # below. These cases are handled later in the function and will
        # remove the description on 1, 2, 3 or 4 if needed, so we do not have
        # to account for those cases here.
        # Note that resets and measurements are included on all data-qubits here.
        # Alias for readability: _sbb <=> Spatial Boundary Basis.
        _sbb = spatial_boundary_basis
        if SpatialArms.UP not in arms:
            corner, bulk = (1, 10) if boundary_is_z else (2, 9)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.UP]
        if SpatialArms.RIGHT not in arms:
            corner, bulk = (4, 21) if boundary_is_z else (2, 22)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][
                PlaquetteOrientation.RIGHT
            ]
        if SpatialArms.DOWN not in arms:
            corner, bulk = (4, 23) if boundary_is_z else (3, 24)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.DOWN]
        if SpatialArms.LEFT not in arms:
            corner, bulk = (1, 12) if boundary_is_z else (3, 11)
            mapping[corner] = mapping[bulk] = two_body_descriptions[_sbb][PlaquetteOrientation.LEFT]

        # For each corner, if the two arms around the corner are not present, the
        # corner plaquette should be removed from the mapping (this is the case
        # where it has been set twice in the ifs above).
        if SpatialArms.LEFT not in arms and SpatialArms.UP not in arms and boundary_is_z:
            del mapping[1]
        if SpatialArms.UP not in arms and SpatialArms.RIGHT not in arms and not boundary_is_z:
            del mapping[2]
        if SpatialArms.DOWN not in arms and SpatialArms.LEFT not in arms and not boundary_is_z:
            del mapping[3]
        if SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms and boundary_is_z:
            del mapping[4]

        ####################
        #       Bulk       #
        ####################
        # Assigning plaquette description to the bulk, considering that the bulk
        # corners (i.e. indices {5, 6, 7, 8}) should be assigned "regular" plaquettes
        # (i.e. 6 is assigned the same plaquette as 17, 7 -> 19, 5 -> 13, 8 -> 15).
        # If these need to be changed, it will be done afterwards.
        # Setting the orientations for Z plaquettes for each of the four portions of
        # the template bulk.
        zup = zdown = Orientation.VERTICAL if boundary_is_z else Orientation.HORIZONTAL
        zright = zleft = zup.flip()
        # If the corresponding arm is missing, the Z plaquette hook error orientation
        # should flip to avoid shortcuts due to hook errors.
        zup = zup if SpatialArms.UP in arms else zup.flip()
        zdown = zdown if SpatialArms.DOWN in arms else zdown.flip()
        zright = zright if SpatialArms.RIGHT in arms else zright.flip()
        zleft = zleft if SpatialArms.LEFT in arms else zleft.flip()
        # The X orientations are the opposite of the Z orientation
        xup, xdown, xright, xleft = (zup.flip(), zdown.flip(), zright.flip(), zleft.flip())

        # Setting the Z plaquettes
        mapping[5] = mapping[13] = bulk_descriptions[Basis.Z][zup]
        mapping[8] = mapping[15] = bulk_descriptions[Basis.Z][zdown]
        mapping[14] = bulk_descriptions[Basis.Z][zright]
        mapping[16] = bulk_descriptions[Basis.Z][zleft]
        # Setting the X plaquettes
        mapping[6] = mapping[17] = bulk_descriptions[Basis.X][xup]
        mapping[7] = mapping[19] = bulk_descriptions[Basis.X][xdown]
        mapping[18] = bulk_descriptions[Basis.X][xright]
        mapping[20] = bulk_descriptions[Basis.X][xleft]

        # For each corner, if the two arms around the corner are not present, the
        # corner plaquette has been removed from the mapping. The corner **within
        # the bulk** should be overwritten to become a 3-body stabilizer measurement.
        # Note that this is not done when deleting the external corners before because
        # the bulk plaquettes are set just above, and so we should override the
        # plaquettes after.
        if SpatialArms.LEFT not in arms and SpatialArms.UP not in arms and boundary_is_z:
            mapping[5] = corner_descriptions[0]
        if SpatialArms.UP not in arms and SpatialArms.RIGHT not in arms and not boundary_is_z:
            mapping[6] = corner_descriptions[1]
        if SpatialArms.DOWN not in arms and SpatialArms.LEFT not in arms and not boundary_is_z:
            mapping[7] = corner_descriptions[2]
        if SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms and boundary_is_z:
            mapping[8] = corner_descriptions[3]

        ####################
        #  Sanity checks   #
        ####################
        # All the plaquettes in the bulk should be set.
        bulk_plaquette_indices = set(range(5, 9)) | set(range(13, 21))
        missing_bulk_plaquette_indices = bulk_plaquette_indices - mapping.keys()
        assert not missing_bulk_plaquette_indices, (
            "Some plaquette(s) in the bulk were not correctly assigned to a "
            f"RPNGDescription. Missing indices: {missing_bulk_plaquette_indices}."
        )
        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())

    def get_spatial_cube_qubit_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC
            gadgets such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_spatial_cube_qubit_raw_template`
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
            TQECError: if ``arms`` only contains 0 or 1 flag.
            TQECError: if ``arms`` describes an I-shaped junction (TOP/DOWN
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
        """Return the :class:`~tqec.templates.base.RectangularTemplate` instance needed to
        implement the given spatial ``arms``.

        Args:
            arms: specification of the spatial arm(s) we want a template for.
                Needs to contain either one arm, or 2 arms that form a line
                (e.g., ``SpatialArms.UP | SpatialArms.DOWN``).

        """
        if (
            len(arms) == 0
            or len(arms) > 2
            or (len(arms) == 2 and arms not in SpatialArms.I_shaped_arms())
        ):
            raise TQECError(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        if SpatialArms.LEFT in arms or SpatialArms.RIGHT in arms:
            return QubitVerticalBorders()
        elif SpatialArms.UP is arms or SpatialArms.DOWN in arms:
            return QubitHorizontalBorders()
        else:
            raise TQECError(f"Unrecognized spatial arm(s): {arms}.")

    def get_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement **one** pipe connecting to a
        spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_spatial_cube_arm_raw_template`
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
            TQECError: if ``arm`` does not contain exactly 1 or 2 flags (i.e.,
                if it contains 0 or 3+ flags).

        Returns:
            a description of the plaquettes needed to implement **one** pipe
            connecting to a spatial cube.

        """
        if len(arms) == 2 and arms not in SpatialArms.I_shaped_arms():
            raise TQECError(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        if arms in [
            SpatialArms.LEFT,
            SpatialArms.RIGHT,
            SpatialArms.LEFT | SpatialArms.RIGHT,
        ]:
            return self._get_left_right_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, arms, linked_cubes, reset, measurement
            )
        if arms in [
            SpatialArms.UP,
            SpatialArms.DOWN,
            SpatialArms.UP | SpatialArms.DOWN,
        ]:
            return self._get_up_down_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, arms, linked_cubes, reset, measurement
            )
        raise TQECError(f"Got an invalid arm: {arms}.")

    def get_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement **one** pipe connecting to a spatial cube.

        Note:
            A spatial cube is defined as a cube with all its spatial boundaries
            in the same basis.
            Such a cube might appear in stability experiments (e.g.,
            http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
            with more than one pipe in the spatial plane) or in other QEC gadgets
            such as the lattice surgery implementation of a ``CZ`` gate.

        Warning:
            This method is tightly coupled with
            :meth:`FixedBulkConventionGenerator.get_spatial_cube_arm_raw_template`
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
            TQECError: if ``arm`` does not contain exactly 1 or 2 flags (i.e.,
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
        # We need the bulk plaquettes to only reset the central qubits of the pipe.
        # To do so, we have two sets of bulk plaquettes with different reset/measured
        # qubits. Plaquettes that should go on the LEFT part of the pipe should
        # measure right qubits (i.e., indices 1 and 3) and conversely for the RIGHT
        # part.
        # Generating plaquette descriptions we will need later.
        left_boundary_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (1, 3))
        right_boundary_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (0, 2))
        two_body_descriptions = self.get_2_body_rpng_descriptions()
        # The hook errors also need to be adapted to the boundary basis.
        zhook = (
            Orientation.HORIZONTAL if spatial_boundary_basis == Basis.Z else Orientation.VERTICAL
        )
        xhook = zhook.flip()
        # List the plaquettes used. This mapping might be corrected afterwards to
        # avoid overwriting 3-body stabilizers introduced by the spatial cube.
        up = 2 if spatial_boundary_basis == Basis.Z else 1
        down = 3 if spatial_boundary_basis == Basis.Z else 4

        mapping = {
            # Boundaries
            # For convenience of definition here, the 2-body stabilizers never reset
            # or measure their data-qubits. If a reset/measurement is needed, it is
            # already included in the plaquettes in the bulk.
            up: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.UP],
            down: two_body_descriptions[spatial_boundary_basis][PlaquetteOrientation.DOWN],
            # LEFT bulk
            5: left_boundary_descriptions[Basis.Z][zhook],
            6: left_boundary_descriptions[Basis.X][xhook],
            # RIGHT bulk
            7: right_boundary_descriptions[Basis.X][xhook],
            8: right_boundary_descriptions[Basis.Z][zhook],
        }

        _corners = self.get_3_body_rpng_descriptions()
        u, v = linked_cubes
        # Alias to reduce clutter in the implementation for corners
        _sbb = spatial_boundary_basis
        # Replaces the top plaquette if it should be a 3-body stabilizer.
        if SpatialArms.LEFT in arms and _sbb == Basis.Z and SpatialArms.UP in v.spatial_arms:
            mapping[up] = _corners[0]
        if SpatialArms.RIGHT in arms and _sbb == Basis.X and SpatialArms.UP in u.spatial_arms:
            mapping[up] = _corners[1]
        # Replaces the bottom plaquette if it should be a 3-body stabilizer.
        if SpatialArms.LEFT in arms and _sbb == Basis.X and SpatialArms.DOWN in v.spatial_arms:
            mapping[down] = _corners[2]
        if SpatialArms.RIGHT in arms and _sbb == Basis.Z and SpatialArms.DOWN in u.spatial_arms:
            mapping[down] = _corners[3]

        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())

    def _get_up_down_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        # We need the bulk plaquettes to only reset the central qubits of the pipe.
        # To do so, we have two sets of bulk plaquettes with different reset/measured
        # qubits. Plaquettes that should go on the UP part of the pipe should measure
        # bottom qubits (i.e., indices 2 and 3) and conversely for the DOWN part.
        # Generating plaquette descriptions we will need later.
        up_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (2, 3))
        down_bulk_descriptions = self.get_bulk_rpng_descriptions(reset, measurement, (0, 1))
        two_body_description = self.get_2_body_rpng_descriptions()
        # The hook errors also need to be adapted to the boundary basis.
        zhook = (
            Orientation.VERTICAL if spatial_boundary_basis == Basis.Z else Orientation.HORIZONTAL
        )
        xhook = zhook.flip()
        # List the plaquettes used. This mapping might be corrected afterwards to
        # avoid overwriting 3-body stabilizers introduced by the spatial cube.
        left = 3 if spatial_boundary_basis == Basis.Z else 1
        right = 2 if spatial_boundary_basis == Basis.Z else 4

        mapping = {
            # Boundaries
            # For convenience of definition here, the 2-body stabilizers never reset
            # or measure their data-qubits. If a reset/measurement is needed, it is
            # already included in the plaquettes in the bulk.
            left: two_body_description[spatial_boundary_basis][PlaquetteOrientation.LEFT],
            right: two_body_description[spatial_boundary_basis][PlaquetteOrientation.RIGHT],
            # TOP bulk
            5: up_bulk_descriptions[Basis.Z][zhook],
            6: up_bulk_descriptions[Basis.X][xhook],
            # BOTTOM bulk
            7: down_bulk_descriptions[Basis.X][xhook],
            8: down_bulk_descriptions[Basis.Z][zhook],
        }

        corners = self.get_3_body_rpng_descriptions()
        u, v = linked_cubes
        # Aliases to reduce clutter in the implementation for corners
        _sbb = spatial_boundary_basis
        # Replaces the top plaquette if it should be a 3-body stabilizer.
        if SpatialArms.UP in arms and _sbb == Basis.Z and SpatialArms.LEFT in v.spatial_arms:
            mapping[left] = corners[0]
        if SpatialArms.UP in arms and _sbb == Basis.X and SpatialArms.RIGHT in v.spatial_arms:
            mapping[right] = corners[1]
        # Replaces the bottom plaquette if it should be a 3-body stabilizer.
        if SpatialArms.DOWN in arms and _sbb == Basis.X and SpatialArms.LEFT in u.spatial_arms:
            mapping[left] = corners[2]
        if SpatialArms.DOWN in arms and _sbb == Basis.Z and SpatialArms.RIGHT in u.spatial_arms:
            mapping[right] = corners[3]

        return FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())

    ############################################################
    #                         Hadamard                         #
    ############################################################

    def get_temporal_hadamard_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.Template` instance needed to implement a
        transversal Hadamard gate applied on one logical qubit.
        """
        return QubitTemplate()

    def get_temporal_hadamard_realignment_plaquettes(
        self, z_orientation: Orientation = Orientation.HORIZONTAL
    ) -> Plaquettes:
        """Return the :class:`.Plaquettes` instance needed to implement the realignment of the bulk
        stabilizer basis of the code.

        This is needed because a transversal Hadamard layer will change the bulk stabilizer basis of
        the code. Under fixed-bulk convention, we use an extra realignment layer to realign the bulk
        stabilizer basis of the code to the original one.

        """
        # plaquettes at the bulk
        x_bulk = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.X,
            z_orientation=z_orientation,
            mq_reset=Basis.X,
            mq_measurement=Basis.Z,
            debug_basis=PauliBasis.X,
        )
        z_bulk = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.Z,
            z_orientation=z_orientation,
            mq_reset=Basis.Z,
            mq_measurement=Basis.X,
            debug_basis=PauliBasis.Z,
        )
        # plaquettes at the right boundary of the template
        right_boundary_basis = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        x_right = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.X,
            z_orientation=z_orientation,
            mq_reset=right_boundary_basis,
            mq_measurement=right_boundary_basis,
            debug_basis=PauliBasis.X if z_orientation == Orientation.VERTICAL else None,
        ).project_on_boundary(PlaquetteOrientation.RIGHT)
        z_right = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.Z,
            z_orientation=z_orientation,
            mq_reset=right_boundary_basis,
            mq_measurement=right_boundary_basis,
            debug_basis=PauliBasis.Z if z_orientation == Orientation.HORIZONTAL else None,
        ).project_on_boundary(PlaquetteOrientation.RIGHT)
        down_boundary_basis = right_boundary_basis.flipped()
        x_down = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.X,
            z_orientation=z_orientation,
            mq_reset=down_boundary_basis,
            mq_measurement=down_boundary_basis,
            debug_basis=PauliBasis.X if z_orientation == Orientation.HORIZONTAL else None,
        ).project_on_boundary(PlaquetteOrientation.DOWN)
        z_down = make_fixed_bulk_realignment_plaquette(
            stabilizer_basis=Basis.Z,
            z_orientation=z_orientation,
            mq_reset=down_boundary_basis,
            mq_measurement=down_boundary_basis,
            debug_basis=PauliBasis.Z if z_orientation == Orientation.VERTICAL else None,
        ).project_on_boundary(PlaquetteOrientation.DOWN)
        realign_mapping = FrozenDefaultDict(
            {9: z_bulk, 10: x_bulk, 11: z_right, 12: x_right, 13: z_down, 14: x_down},
            default_value=self._mapper.get_plaquette(RPNGDescription.empty()),
        )
        return Plaquettes(realign_mapping)

    ########################################
    #                X pipe                #
    ########################################
    def get_spatial_vertical_hadamard_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.Template` instance needed to implement a spatial
        Hadamard pipe between two logical qubits aligned on the ``X`` axis.
        """
        raise self._not_implemented_exception()

    def get_spatial_vertical_hadamard_rpng_descriptions(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a Hadamard spatial transition
        between two neighbouring logical qubits aligned on the ``X`` axis.

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
        raise self._not_implemented_exception()  # pragma: no cover

    def get_spatial_vertical_hadamard_plaquettes(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a Hadamard spatial transition between two
        neighbouring logical qubits aligned on the ``X`` axis.

        The Hadamard transition basically exchanges the ``X`` and ``Z`` logical
        observables between two neighbouring logical qubits aligned on the ``X``
        axis.

        Note:
            By convention, the hadamard-like transition is performed at the
            top-most plaquettes.

        Warning:
            This method is tightly coupled with
            :meth:`PlaquetteGenerator.get_spatial_vertical_hadamard_raw_template` and the returned
            plaquettes should only be considered valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this method.

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
            the plaquettes needed to implement a Hadamard spatial transition between two
            neighbouring logical qubits aligned on the ``X`` axis.

        """
        return self._mapper(self.get_spatial_vertical_hadamard_rpng_descriptions)(
            top_left_is_z_stabilizer, reset, measurement
        )

    ########################################
    #                Y pipe                #
    ########################################
    def get_spatial_horizontal_hadamard_raw_template(self) -> RectangularTemplate:
        """Return the :class:`~tqec.templates.base.Template` instance needed to implement a spatial
        Hadamard pipe between two neighbouring logical qubits aligned on the ``Y`` axis.
        """
        raise self._not_implemented_exception()

    def get_spatial_horizontal_hadamard_rpng_descriptions(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return a description of the plaquettes needed to implement a Hadamard spatial transition
        between two neighbouring logical qubits aligned on the ``Y`` axis.

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
        raise self._not_implemented_exception()  # pragma: no cover

    def get_spatial_horizontal_hadamard_plaquettes(
        self,
        top_left_is_z_stabilizer: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        """Return the plaquettes needed to implement a Hadamard spatial transition between two
        neighbouring logical qubits aligned on the ``Y`` axis.

        The Hadamard transition basically exchanges the ``X`` and ``Z`` logical
        observables between two neighbouring logical qubits aligned on the ``Y``
        axis.

        Note:
            By convention, the hadamard-like transition is performed at the
            top-most plaquettes.

        Warning:
            This method is tightly coupled with
            :meth:`PlaquetteGenerator.get_spatial_horizontal_hadamard_raw_template` and the returned
            plaquettes should only be considered valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this method.

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
            the plaquettes needed to implement a Hadamard spatial transition between two
            neighbouring logical qubits aligned on the ``Y`` axis.

        """
        return self._mapper(self.get_spatial_horizontal_hadamard_rpng_descriptions)(
            top_left_is_z_stabilizer, reset, measurement
        )
