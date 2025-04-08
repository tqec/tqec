from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Literal

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.utils import PlaquetteMapper
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation, PlaquetteSide
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.instructions import (
    MEASUREMENT_INSTRUCTION_NAMES,
    RESET_INSTRUCTION_NAMES,
)


def _get_spatial_cube_arm_name(
    basis: Basis,
    reset: Basis | None,
    measurement: Basis | None,
    position: Literal["UP", "DOWN"],
    is_reverse: bool,
) -> str:
    parts = ["SpatialCubeArm", basis.value.upper(), position]
    if is_reverse:
        parts.append("reversed")
    if reset is not None:
        parts.append(f"reset({reset.value.upper()})")
    if measurement is not None:
        parts.append(f"datameas({measurement.value.upper()})")
    return "_".join(parts)


def _make_spatial_cube_arm_memory_moments_up(
    basis: Basis, is_reverse: bool
) -> list[Moment]:
    """
    Implement circuit for the following plaquette::

        0 ----- 1
        |       |
        |   4   |
        |       |
        2 -----
    """
    args = [1, 0] if is_reverse else [0, 1]
    b = basis.name.upper()
    return [
        Moment(stim.Circuit("RX 4\nRZ 2")),
        Moment(stim.Circuit("CX 4 2")),
        Moment(stim.Circuit(f"C{b} 4 {args[0]}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit(f"C{b} 4 {args[1]}")),
        Moment(stim.Circuit("CX 2 4")),
    ]


def _make_spatial_cube_arm_memory_moments_down(
    basis: Basis, is_reverse: bool
) -> list[Moment]:
    """
    Implement circuit for the following plaquette::

        0 -----
        |       |
        |   4   |
        |       |
        2 ----- 3

        1 -----
        |       |
        |   0   |
        |       |
        3 ----- 4
    """
    args = [3, 2] if is_reverse else [2, 3]
    b = basis.name.upper()
    return [
        Moment(stim.Circuit("RZ 0")),
        Moment(stim.Circuit("RZ 4")),
        Moment(stim.Circuit("CX 0 4")),
        Moment(stim.Circuit(f"C{b} 4 {args[0]}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit(f"C{b} 4 {args[1]}")),
        Moment(stim.Circuit("CX 4 0")),
        Moment(stim.Circuit("MX 4")),
    ]


def make_spatial_cube_arm_plaquettes(
    basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reverse: bool = False,
) -> tuple[Plaquette, Plaquette]:
    """Make a plaquette for spatial cube arms.

    The below text represents the qubits in a stretched stabilizer ::

        a ----- b
        |       |
        |   c   |
        |       |
        d ------
        |       |
        |   e   |
        |       |
        f ----- g

    This is split into two plaquettes, with ``UP`` being ``(a, b, c, d)`` and
    ``DOWN`` being ``(d, e, f, g)``.

    Args:
        basis: the basis of the plaquette.
        reset: the logical basis for data qubit initialization. Defaults to
            ``None`` which means "no initialization of data qubits".
        measurement: the logical basis for data qubit measurement. Defaults to
            ``None`` means "no measurement of data qubits".
        is_reverse: whether the schedules of controlled-A gates are reversed.

    Returns:
        A tuple ``(UP, DOWN)`` containing the two plaquettes needed to implement
        spatial cube arms.
    """
    up_moments = _make_spatial_cube_arm_memory_moments_up(basis, is_reverse)
    down_moments = _make_spatial_cube_arm_memory_moments_down(basis, is_reverse)

    qubits = SquarePlaquetteQubits()
    qubit_map = qubits.qubit_map
    up_qubits = [qubit_map[q] for q in qubits.get_qubits_on_side(PlaquetteSide.UP)]
    down_qubits = [qubit_map[q] for q in qubits.get_qubits_on_side(PlaquetteSide.DOWN)]

    b = basis.value.upper()
    if reset is not None:
        up_moments[0].append(f"R{b}", down_qubits, [])
        down_moments[0].append(f"R{b}", up_qubits, [])
    if measurement is not None:
        up_moments[-1].append(f"M{b}", down_qubits, [])
        down_moments[-1].append(f"M{b}", up_qubits, [])

    mergeable_instructions = MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES

    return (
        Plaquette(
            _get_spatial_cube_arm_name(basis, reset, measurement, "UP", is_reverse),
            qubits,
            ScheduledCircuit(up_moments, 0, qubit_map),
            mergeable_instructions,
        ),
        Plaquette(
            _get_spatial_cube_arm_name(basis, reset, measurement, "DOWN", is_reverse),
            qubits,
            ScheduledCircuit(down_moments, 0, qubit_map),
            mergeable_instructions,
        ),
    )


@dataclass(frozen=True)
class ExtendedPlaquette:
    top: Plaquette
    bottom: Plaquette


@dataclass(frozen=True)
class ExtendedPlaquetteCollection:
    bulk: ExtendedPlaquette
    left_with_arm: ExtendedPlaquette
    left_without_arm: ExtendedPlaquette
    right_with_arm: ExtendedPlaquette
    right_without_arm: ExtendedPlaquette

    @staticmethod
    def from_args(
        basis: Basis, reset: Basis, measurement: Basis, is_reverse: bool
    ) -> ExtendedPlaquetteCollection:
        up, down = make_spatial_cube_arm_plaquettes(
            basis, reset, measurement, is_reverse
        )
        return ExtendedPlaquetteCollection(
            bulk=ExtendedPlaquette(up, down),
            left_with_arm=ExtendedPlaquette(
                up.project_on_data_qubit_indices([1, 2, 3]), down
            ),
            left_without_arm=ExtendedPlaquette(
                up.project_on_data_qubit_indices([1, 3]),
                down.project_on_data_qubit_indices([1, 3]),
            ),
            right_with_arm=ExtendedPlaquette(
                up, down.project_on_data_qubit_indices([0, 1, 2])
            ),
            right_without_arm=ExtendedPlaquette(
                up.project_on_data_qubit_indices([0, 2]),
                down.project_on_data_qubit_indices([0, 2]),
            ),
        )


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
        PO = PlaquetteOrientation
        return {
            Basis.X: {
                PO.DOWN: RPNGDescription.from_string("-x1- -x2- ---- ----"),
                PO.LEFT: RPNGDescription.from_string("---- -x2- ---- -x5-"),
                PO.UP: RPNGDescription.from_string("---- ---- -x3- -x5-"),
                PO.RIGHT: RPNGDescription.from_string("-x1- ---- -x3- ----"),
            },
            Basis.Z: {
                PO.DOWN: RPNGDescription.from_string("-z1- -z2- ---- ----"),
                PO.LEFT: RPNGDescription.from_string("---- -z2- ---- -z5-"),
                PO.UP: RPNGDescription.from_string("---- ---- -z3- -z5-"),
                PO.RIGHT: RPNGDescription.from_string("-z1- ---- -z3- ----"),
            },
        }

    def get_extended_plaquettes(
        self, reset: Basis, measurement: Basis
    ) -> dict[Basis, tuple[ExtendedPlaquetteCollection, ExtendedPlaquetteCollection]]:
        """Get plaquettes that are supposed to be used to implement ``UP`` or
        ``DOWN`` spatial pipes.

        Returns:
            a map from stabilizer basis to a pair of
            :class:`ExtendedPlaquetteCollection`. The first entry of the pair
            contains plaquettes that have not been reversed, the second entry
            contains plaquettes that have been reversed.
        """
        return {
            b: (
                ExtendedPlaquetteCollection.from_args(b, reset, measurement, False),
                ExtendedPlaquetteCollection.from_args(b, reset, measurement, True),
            )
            for b in Basis
        }

    ############################################################
    #                          Memory                          #
    ############################################################

    ########################################
    #             Regular qubit            #
    ########################################
    def get_memory_qubit_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a single logical qubit."""
        return QubitTemplate()

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
            :meth:`FixedParityConventionGenerator.get_memory_qubit_raw_template`
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
        # Basis for top/bottom and left/right boundary plaquettes
        HBASIS = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        VBASIS = HBASIS.flipped()
        # BPs: Bulk Plaquettes.
        BPs = self.get_bulk_rpng_descriptions(reset, measurement)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions()
        return FrozenDefaultDict(
            {
                6: TBPs[VBASIS][PlaquetteOrientation.UP],
                7: TBPs[HBASIS][PlaquetteOrientation.LEFT],
                # Bulk
                9: BPs[VBASIS][Orientation.HORIZONTAL],
                10: BPs[HBASIS][Orientation.VERTICAL],
                12: TBPs[HBASIS][PlaquetteOrientation.RIGHT],
                13: TBPs[VBASIS][PlaquetteOrientation.DOWN],
            },
            default_value=RPNGDescription.empty(),
        )

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
            :meth:`FixedParityConventionGenerator.get_memory_qubit_raw_template`
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
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement a regular spatial pipe between two logical
        qubits aligned on the ``X`` axis."""
        return QubitVerticalBorders()

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
            :meth:`FixedParityConventionGenerator.get_memory_vertical_boundary_raw_template`
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
        # Basis for top/bottom boundary plaquettes
        VBASIS = Basis.Z if z_orientation == Orientation.VERTICAL else Basis.X
        HBASIS = VBASIS.flipped()
        # BPs: Bulk Plaquettes.
        BPs_LEFT = self.get_bulk_rpng_descriptions(reset, measurement, (1, 3))
        BPs_RIGHT = self.get_bulk_rpng_descriptions(reset, measurement, (0, 2))
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions()

        return FrozenDefaultDict(
            {
                2: TBPs[VBASIS][PlaquetteOrientation.UP],
                3: TBPs[VBASIS][PlaquetteOrientation.DOWN],
                # LEFT bulk
                5: BPs_LEFT[VBASIS][Orientation.HORIZONTAL],
                6: BPs_LEFT[HBASIS][Orientation.VERTICAL],
                # RIGHT bulk
                7: BPs_RIGHT[HBASIS][Orientation.VERTICAL],
                8: BPs_RIGHT[VBASIS][Orientation.HORIZONTAL],
            },
            default_value=RPNGDescription.empty(),
        )

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
            :meth:`FixedParityConventionGenerator.get_memory_vertical_boundary_raw_template`
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
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a regular spatial pipe between two logical qubits
        aligned on the ``Y`` axis."""
        return QubitHorizontalBorders()

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
            :meth:`FixedParityConventionGenerator.get_memory_horizontal_boundary_raw_template`
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
        # Basis for left/right boundary plaquettes
        HBASIS = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        VBASIS = HBASIS.flipped()
        # BPs: Bulk Plaquettes.
        BPs_UP = self.get_bulk_rpng_descriptions(reset, measurement, (2, 3))
        BPs_DOWN = self.get_bulk_rpng_descriptions(reset, measurement, (0, 1))
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions()

        return FrozenDefaultDict(
            {
                1: TBPs[HBASIS][PlaquetteOrientation.LEFT],
                4: TBPs[HBASIS][PlaquetteOrientation.RIGHT],
                # TOP bulk
                5: BPs_UP[VBASIS][Orientation.HORIZONTAL],
                6: BPs_UP[HBASIS][Orientation.VERTICAL],
                # BOTTOM bulk
                7: BPs_DOWN[HBASIS][Orientation.VERTICAL],
                8: BPs_DOWN[VBASIS][Orientation.HORIZONTAL],
            },
            default_value=RPNGDescription.empty(),
        )

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
            :meth:`FixedParityConventionGenerator.get_memory_horizontal_boundary_raw_template`
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
            :meth:`FixedParityConventionGenerator.get_spatial_cube_qubit_raw_template`
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
            :meth:`FixedParityConventionGenerator.get_spatial_cube_qubit_raw_template`
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
    def get_spatial_cube_arm_raw_template(
        self, arms: SpatialArms
    ) -> RectangularTemplate:
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
            :meth:`FixedParityConventionGenerator.get_spatial_cube_arm_raw_template`
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
            :meth:`FixedParityConventionGenerator.get_spatial_cube_arm_raw_template`
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

    def get_temporal_hadamard_plaquettes(
        self, z_orientation: Orientation = Orientation.HORIZONTAL
    ) -> Plaquettes:
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
