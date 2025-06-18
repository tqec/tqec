from __future__ import annotations

import inspect
from typing import ClassVar, Final, Literal

from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.extended_stabilizers import (
    ExtendedPlaquetteCollection,
)
from tqec.compile.specs.library.generators.utils import PlaquetteMapper
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import Direction3D


class FixedParityConventionGenerator:
    VSCHED: ClassVar[dict[bool, tuple[int, int, int, int]]] = {
        False: (1, 4, 3, 5),
        True: (5, 3, 4, 1),
    }
    HSCHED: ClassVar[dict[bool, tuple[int, int, int, int]]] = {
        False: (1, 2, 3, 5),
        True: (5, 3, 2, 1),
    }

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
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
        reset_and_measured_indices: tuple[Literal[0, 1, 2, 3], ...] = (0, 1, 2, 3),
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        """Get plaquettes that are supposed to be used in the bulk.

        This function returns the four 4-body stabilizer measurement plaquettes
        containing 5 rounds that can be arbitrarily tiled without any gate schedule
        clash. These plaquettes are organised by basis and hook orientation.

        Args:
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        vsched = FixedParityConventionGenerator.VSCHED[is_reversed]
        hsched = FixedParityConventionGenerator.HSCHED[is_reversed]
        return {
            basis: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"{r}{basis.value.lower()}{s}{m}" for r, s, m in zip(rs, vsched, ms))
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"{r}{basis.value.lower()}{s}{m}" for r, s, m in zip(rs, hsched, ms))
                ),
            }
            for basis in Basis
        }

    def get_3_body_rpng_descriptions(
        self,
        basis: Basis,
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
        b = basis.value.lower()
        # r/m: reset/measurement basis applied to each data-qubit
        r = reset.value.lower() if reset is not None else "-"
        m = measurement.value.lower() if measurement is not None else "-"
        # Note: the schedule of CNOT gates in corner plaquettes is less important
        # because hook errors do not exist on 3-body stabilizers. We arbitrarily
        # chose the vertical schedule.
        s = FixedParityConventionGenerator.VSCHED[is_reversed]
        # Note that we include resets and measurements on all the used data-qubits.
        # That should be fine because this plaquette only touches cubes and pipes
        # that are related to the spatial junction being implemented, and it is not
        # valid to have a temporal pipe coming from below a spatial junction, hence
        # the data-qubits cannot be already initialised to a value we would like to
        # keep and that would be destroyed by reset/measurement.
        return (
            RPNGDescription.from_string(f"---- {r}{b}{s[1]}{m} {r}{b}{s[2]}{m} {r}{b}{s[3]}{m}"),
            RPNGDescription.from_string(f"{r}{b}{s[0]}{m} ---- {r}{b}{s[2]}{m} {r}{b}{s[3]}{m}"),
            RPNGDescription.from_string(f"{r}{b}{s[0]}{m} {r}{b}{s[1]}{m} ---- {r}{b}{s[3]}{m}"),
            RPNGDescription.from_string(f"{r}{b}{s[0]}{m} {r}{b}{s[1]}{m} {r}{b}{s[2]}{m} ----"),
        )

    def get_2_body_rpng_descriptions(
        self, is_reversed: bool, hadamard: bool = False
    ) -> dict[Basis, dict[PlaquetteOrientation, RPNGDescription]]:
        """Get plaquettes that are supposed to be used on the boundaries.

        This function returns the eight 2-body stabilizer measurement plaquettes
        that can be used on the 5-round plaquettes returned by
        :meth:`get_bulk_plaquettes`.

        Args:
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
            hadamard: ``True`` if the plaquette should contain a Hadamard gate.

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
        h = "h" if hadamard else "-"
        ret: dict[Basis, dict[PlaquetteOrientation, RPNGDescription]] = {}
        # Note: the schedule of CNOT gates in weight-2 plaquettes is less
        # important because hook errors do not exist. We arbitrarily chose the
        # vertical schedule.
        s = FixedParityConventionGenerator.VSCHED[is_reversed]
        for basis in Basis:
            b = basis.value.lower()
            ret[basis] = {
                PO.DOWN: RPNGDescription.from_string(f"-{b}{s[0]}{h} -{b}{s[1]}{h} ---- ----"),
                PO.LEFT: RPNGDescription.from_string(f"---- -{b}{s[1]}{h} ---- -{b}{s[3]}{h}"),
                PO.UP: RPNGDescription.from_string(f"---- ---- -{b}{s[2]}{h} -{b}{s[3]}{h}"),
                PO.RIGHT: RPNGDescription.from_string(f"-{b}{s[0]}{h} ---- -{b}{s[2]}{h} ----"),
            }
        return ret

    def get_extended_plaquettes(
        self, reset: Basis | None, measurement: Basis | None, is_reversed: bool
    ) -> dict[Basis, ExtendedPlaquetteCollection]:
        """Get plaquettes that are supposed to be used to implement ``UP`` or
        ``DOWN`` spatial pipes.

        Returns:
            a map from stabilizer basis to a pair of
            :class:`ExtendedPlaquetteCollection`. The first entry of the pair
            contains plaquettes that have not been reversed, the second entry
            contains plaquettes that have been reversed.

        """
        return {
            b: (ExtendedPlaquetteCollection.from_args(b, reset, measurement, is_reversed))
            for b in Basis
        }

    def get_bulk_hadamard_rpng_descriptions(
        self, is_reversed: bool
    ) -> dict[Basis, dict[Orientation, RPNGDescription]]:
        # 2-qubit gate schedules
        vsched = FixedParityConventionGenerator.VSCHED[is_reversed]
        hsched = FixedParityConventionGenerator.HSCHED[is_reversed]
        return {
            basis: {
                Orientation.VERTICAL: RPNGDescription.from_string(
                    " ".join(f"-{basis.value.lower()}{s}h" for s in vsched)
                ),
                Orientation.HORIZONTAL: RPNGDescription.from_string(
                    " ".join(f"-{basis.value.lower()}{s}h" for s in hsched)
                ),
            }
            for basis in Basis
        }

    def get_spatial_x_hadamard_rpng_descriptions(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription]:
        """Returns a description of the 3 different plaquettes needed to perform
        a spatial hadamard transformation between two qubits aligned on the X
        axis.

        Args:
            top_left_basis: basis of the stabilizer measured by the top-left
                data-qubit.
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
            reset: basis of the reset operation performed on data-qubits. Defaults
                to ``None`` that translates to no reset being applied on data-qubits.
            measurement: basis of the measurement operation performed on data-qubits.
                Defaults to ``None`` that translates to no measurement being applied
                on data-qubits.

        Returns:
            a tuple ``(bulk1, bulk2, bottom)`` containing:

            - ``bulk1``, a square plaquette with its two left-most data-qubits
              measuring ``top_left_basis`` stabilizer.
            - ``bulk2``, a square plaquette with its two left-most data-qubits
              measuring ``top_left_basis.flipped()`` stabilizer.
            - ``bottom``, a plaquette measuring a weight 2 stabilizer with its
              left-most data-qubit measuring ``top_left_basis`` stabilizer and
              right-most data-qubit measuring ``top_left_basis.flipped()``
              stabilizer.

        """
        b = top_left_basis.value.lower()
        o = top_left_basis.flipped().value.lower()
        r = reset.value.lower() if reset is not None else "-"
        m = measurement.value.lower() if measurement is not None else "-"
        # 2-qubit gate schedules
        vs = FixedParityConventionGenerator.VSCHED[is_reversed]
        hs = FixedParityConventionGenerator.HSCHED[is_reversed]
        return (
            RPNGDescription.from_string(
                f"-{b}{hs[0]}- {r}{o}{hs[1]}{m} -{b}{hs[2]}- {r}{o}{hs[3]}{m}"
            ),
            RPNGDescription.from_string(
                f"-{o}{vs[0]}- {r}{b}{vs[1]}{m} -{o}{vs[2]}- {r}{b}{vs[3]}{m}"
            ),
            RPNGDescription.from_string(f"-{b}{hs[0]}- {r}{o}{hs[1]}{m} ---- ----"),
        )

    def get_spatial_y_hadamard_rpng_descriptions(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription]:
        """Returns a description of the 3 different plaquettes needed to perform
        a spatial hadamard transformation between two qubits aligned on the Y
        axis.

        Args:
            top_left_basis: basis of the top-left-most stabilizer (top
                stabilizer of a 2-qubit plaquette).
            reset: basis of the reset operation performed on data-qubits. Defaults
                to ``None`` that translates to no reset being applied on data-qubits.
            measurement: basis of the measurement operation performed on data-qubits.
                Defaults to ``None`` that translates to no measurement being applied
                on data-qubits.

        Returns:
            a tuple ``(bulk1, bulk2, left)`` containing:

            - ``bulk1``, a square plaquette with its two top-most data-qubits
              measuring ``top_left_basis`` stabilizer.
            - ``bulk2``, a square plaquette with its two left-most data-qubits
              measuring ``top_left_basis.flipped()`` stabilizer.
            - ``left``, a plaquette measuring a weight 2 stabilizer with its
              top-most data-qubit measuring ``top_left_basis`` stabilizer and
              bottom-most data-qubit measuring ``top_left_basis.flipped()``
              stabilizer.

        Warning:
            When seen visually, the plaquettes returned by this method are not
            in reading order. Visually, the order is::

                left  |  bulk1  |  bulk2

            but this method returns ``(bulk1, bulk2, left)``.

        """
        b = top_left_basis.value.lower()
        o = top_left_basis.flipped().value.lower()
        r = reset.value.lower() if reset is not None else "-"
        m = measurement.value.lower() if measurement is not None else "-"
        # 2-qubit gate schedules
        vs = FixedParityConventionGenerator.VSCHED[is_reversed]
        hs = FixedParityConventionGenerator.HSCHED[is_reversed]
        return (
            RPNGDescription.from_string(
                f"-{o}{hs[0]}- -{o}{hs[1]}{m} {r}{b}{hs[2]}- {r}{b}{hs[3]}{m}"
            ),
            RPNGDescription.from_string(
                f"-{b}{vs[0]}- -{b}{vs[1]}{m} {r}{o}{vs[2]}- {r}{o}{vs[3]}{m}"
            ),
            RPNGDescription.from_string(f"---- -{b}{vs[1]}- ---- {r}{o}{vs[3]}{m}"),
        )

    ############################################################
    #                          Memory                          #
    ############################################################

    ########################################
    #             Regular qubit            #
    ########################################
    def get_memory_qubit_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a single logical qubit.
        """
        return QubitTemplate()

    def get_memory_qubit_rpng_descriptions(
        self,
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        BPs = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)
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
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
            is_reversed, z_orientation, reset, measurement
        )

    ########################################
    #                X pipe                #
    ########################################
    def get_memory_vertical_boundary_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement a regular spatial pipe between two logical
        qubits aligned on the ``X`` axis.
        """
        return QubitVerticalBorders()

    def get_memory_vertical_boundary_rpng_descriptions(
        self,
        is_reversed: bool,
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
        BPs_LEFT = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement, (1, 3))
        BPs_RIGHT = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement, (0, 2))
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)

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
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
            is_reversed, z_orientation, reset, measurement
        )

    ########################################
    #                Y pipe                #
    ########################################
    def get_memory_horizontal_boundary_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate` instance
        needed to implement a regular spatial pipe between two logical qubits
        aligned on the ``Y`` axis.
        """
        return QubitHorizontalBorders()

    def get_memory_horizontal_boundary_rpng_descriptions(
        self,
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        BPs_UP = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement, (2, 3))
        BPs_DOWN = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement, (0, 1))
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)

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
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
            is_reversed, z_orientation, reset, measurement
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
        return QubitSpatialCubeTemplate()

    def get_spatial_cube_qubit_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
            reset: basis of the reset operation performed on data-qubits.
                Defaults to ``None`` that translates to no reset being applied
                on data-qubits.
            measurement: basis of the measurement operation performed on
                data-qubits. Defaults to ``None`` that translates to no
                measurement being applied on data-qubits.

        Raises:
            TQECException: if ``arms`` describes an I-shaped junction (TOP/DOWN
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
            raise TQECException(
                "I-shaped spatial junctions (i.e., spatial junctions with only two "
                "arms that are the opposite of each other: LEFT/RIGHT or UP/DOWN) "
                "should not use get_spatial_cube_qubit_template but rather use "
                "a conventional memory logical qubit with get_memory_qubit_template."
            )
        # SBB: Spatial Boundary Basis.
        SBB = spatial_boundary_basis
        # Pre-define some collection of plaquettes
        # CSs: Corner Stabilizers (3-body stabilizers).
        CSs = self.get_3_body_rpng_descriptions(SBB, is_reversed, reset, measurement)
        # BPs: Bulk Plaquettes.
        BPs = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement)
        # TBPs: Two-Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)

        if arms == SpatialArms.NONE:
            # Stability experiment
            return FrozenDefaultDict(
                {
                    5: CSs[0],
                    6: BPs[SBB.flipped()][Orientation.VERTICAL],
                    7: BPs[SBB.flipped()][Orientation.VERTICAL],
                    8: CSs[3],
                    10: TBPs[SBB][PlaquetteOrientation.UP],
                    12: TBPs[SBB][PlaquetteOrientation.LEFT],
                    13: BPs[SBB][Orientation.HORIZONTAL],
                    14: BPs[SBB][Orientation.VERTICAL],
                    15: BPs[SBB][Orientation.HORIZONTAL],
                    16: BPs[SBB][Orientation.VERTICAL],
                    17: BPs[SBB.flipped()][Orientation.VERTICAL],
                    18: BPs[SBB.flipped()][Orientation.HORIZONTAL],
                    19: BPs[SBB.flipped()][Orientation.VERTICAL],
                    20: BPs[SBB.flipped()][Orientation.HORIZONTAL],
                    21: TBPs[SBB][PlaquetteOrientation.RIGHT],
                    23: TBPs[SBB][PlaquetteOrientation.DOWN],
                },
                default_value=RPNGDescription.empty(),
            )
        # Note about the fixed parity convention: in order to work as expected,
        # spatial cubes need to have one dimension that does not respect the
        # parity convention. By convention, we only use stretched stabilizers in
        # the vertical (Y) dimension (i.e., between two cubes that are aligned
        # on the Y axis), and so only the boundaries on the X axis (left and
        # right) need to not follow the fixed parity convention.
        # For spatial cubes, the only exception to the above rule is when the
        # cube is a "dead-end" (i.e., only one spatial arm: ``len(arms) == 1``).
        # In that case, the dimension that should not follow the fixed parity
        # convention is the one "closing" the pipe, i.e., the dimension in which
        # the only arm is positioned.
        # For dead-end cubes, a dead-end in the X dimension still follows the
        # general rule (the boundaries in the X axis do not follow the
        # convention), so we only have to test if we have a dead-end in the Y
        # dimension.
        ODD_BOUNDARY_DIMENSION: Final[Literal[Direction3D.X, Direction3D.Y]] = (
            Direction3D.Y if arms in [SpatialArms.UP, SpatialArms.DOWN] else Direction3D.X
        )

        mapping: dict[int, RPNGDescription] = {}

        ####################
        #    Boundaries    #
        ####################
        # Fill the boundaries that should be filled in the returned template
        # because they have no arms, and so will not be filled later.
        TOP, BOTTOM, LEFT, RIGHT = (
            (10, 23, 12, 21) if ODD_BOUNDARY_DIMENSION == Direction3D.X else (9, 24, 11, 22)
        )
        if SpatialArms.UP not in arms:
            mapping[TOP] = TBPs[SBB][PlaquetteOrientation.UP]
        if SpatialArms.RIGHT not in arms:
            mapping[RIGHT] = TBPs[SBB][PlaquetteOrientation.RIGHT]
        if SpatialArms.DOWN not in arms:
            mapping[BOTTOM] = TBPs[SBB][PlaquetteOrientation.DOWN]
        if SpatialArms.LEFT not in arms:
            mapping[LEFT] = TBPs[SBB][PlaquetteOrientation.LEFT]

        ####################
        #       Bulk       #
        ####################
        # Bulk plaquettes basis might change according to the odd boundary
        # dimension to avoid having 2 plaquettes measuring the same basis side
        # by side.
        # TLB, OTB: Top-Left (plaquette) Basis, Other Basis (for the bulk)
        TLB = SBB if ODD_BOUNDARY_DIMENSION == Direction3D.X else SBB.flipped()
        OTB = TLB.flipped()
        # Assigning plaquette description to the bulk, considering that the bulk
        # corners (i.e. indices {5, 6, 7, 8}) should be assigned "regular" plaquettes
        # (i.e. 6 is assigned the same plaquette as 17, 7 -> 19, 5 -> 13, 8 -> 15).
        # If these need to be changed, it will be done afterwards.
        # Setting the orientations for SBB plaquettes for each of the four
        # portions of the template bulk.
        SBB_UP = SBB_DOWN = Orientation.VERTICAL
        SBB_RIGHT = SBB_LEFT = Orientation.HORIZONTAL
        # If the corresponding arm is missing, the SBB plaquette hook error
        # orientation should flip to avoid shortcuts due to hook errors.
        SBB_UP = SBB_UP if SpatialArms.UP in arms else SBB_UP.flip()
        SBB_DOWN = SBB_DOWN if SpatialArms.DOWN in arms else SBB_DOWN.flip()
        SBB_RIGHT = SBB_RIGHT if SpatialArms.RIGHT in arms else SBB_RIGHT.flip()
        SBB_LEFT = SBB_LEFT if SpatialArms.LEFT in arms else SBB_LEFT.flip()
        # The OTH (other basis) orientations are the opposite of the SBB
        # orientation.
        OTH_UP, OTH_DOWN = SBB_UP.flip(), SBB_DOWN.flip()
        OTH_RIGHT, OTH_LEFT = SBB_RIGHT.flip(), SBB_LEFT.flip()

        # Setting the SBB plaquettes
        mapping[5] = mapping[13] = BPs[TLB][SBB_UP]
        mapping[8] = mapping[15] = BPs[TLB][SBB_DOWN]
        mapping[14] = BPs[TLB][SBB_RIGHT]
        mapping[16] = BPs[TLB][SBB_LEFT]
        # Setting the OTH plaquettes
        mapping[6] = mapping[17] = BPs[OTB][OTH_UP]
        mapping[7] = mapping[19] = BPs[OTB][OTH_DOWN]
        mapping[18] = BPs[OTB][OTH_RIGHT]
        mapping[20] = BPs[OTB][OTH_LEFT]

        # For the in-bulk corners, if the two arms around the corner are not
        # present, the corner plaquette has been removed from the mapping. The
        # corner **within the bulk** should be overwritten to become a 3-body
        # stabilizer measurement.
        if arms == SpatialArms.RIGHT:
            mapping[5] = CSs[0]
        elif arms == SpatialArms.DOWN:
            mapping[6] = CSs[1]
        elif arms == SpatialArms.UP:
            mapping[7] = CSs[2]
        elif arms == SpatialArms.LEFT:
            mapping[8] = CSs[3]
        # At this point, we are sure that len(arms) >= 2. The only cases left
        # where a 3-body stabilizer is needed are the following:
        if arms == SpatialArms.RIGHT | SpatialArms.DOWN:
            mapping[5] = CSs[0]
        if arms == SpatialArms.LEFT | SpatialArms.UP:
            mapping[8] = CSs[3]

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
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
            spatial_boundary_basis, arms, is_reversed, reset, measurement
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
                If the arm that should be built has one spatial cube on top,
                this should be ``SpatialArm.DOWN`` because it is the bottom arm
                of a spatial cube.
                If the arm links 2 spatial cubes, the ``arms`` parameter should
                be the union of the arms (and so can only be
                ``SpatialArms.UP | SpatialArms.DOWN`` or
                ``SpatialArms.LEFT | SpatialArms.RIGHT`` because any other
                combination cannot be formed by a single arm).

        Raises:
            TQECException: if the provided ``arms`` value does not check the
                documented pre-conditions.

        """
        if (
            len(arms) == 0
            or len(arms) > 2
            or (len(arms) == 2 and arms not in SpatialArms.I_shaped_arms())
        ):
            raise TQECException(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        if SpatialArms.LEFT in arms or SpatialArms.RIGHT in arms:
            return QubitVerticalBorders()
        elif SpatialArms.UP is arms or SpatialArms.DOWN in arms:
            return QubitHorizontalBorders()
        else:
            raise TQECException(f"Unrecognized spatial arm(s): {arms}.")

    def get_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        is_reversed: bool,
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
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        if len(arms) == 2 and arms not in SpatialArms.I_shaped_arms():
            raise TQECException(
                f"The two provided arms cannot form a spatial pipe. Got {arms} but "
                f"expected either a single {SpatialArms.__name__} or two but in a "
                f"line (e.g., {SpatialArms.I_shaped_arms()})."
            )
        if arms in [
            SpatialArms.LEFT,
            SpatialArms.RIGHT,
            SpatialArms.LEFT | SpatialArms.RIGHT,
        ]:
            return self._get_left_right_spatial_cube_arm_plaquettes(
                spatial_boundary_basis,
                arms,
                linked_cubes,
                is_reversed,
                reset,
                measurement,
            )
        if arms in [
            SpatialArms.UP,
            SpatialArms.DOWN,
            SpatialArms.UP | SpatialArms.DOWN,
        ]:
            return self._get_up_down_spatial_cube_arm_plaquettes(
                spatial_boundary_basis,
                arms,
                linked_cubes,
                is_reversed,
                reset,
                measurement,
            )
        raise TQECException(f"Got an invalid arm: {arms}.")

    def _get_left_right_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        # This is a regular memory arm, except that we should make sure that one
        # of the boundary does not override the extended stabilizer.
        z_orientation = (
            Orientation.VERTICAL if spatial_boundary_basis == Basis.Z else Orientation.HORIZONTAL
        )
        regular_memory = self.get_memory_vertical_boundary_plaquettes(
            is_reversed, z_orientation, reset, measurement
        )
        u, v = linked_cubes
        if SpatialArms.LEFT in arms and SpatialArms.UP in v.spatial_arms:
            regular_memory = regular_memory.without_plaquettes([2])
        if SpatialArms.RIGHT in arms and SpatialArms.DOWN in u.spatial_arms:
            regular_memory = regular_memory.without_plaquettes([3])
        return regular_memory

    @staticmethod
    def pipe_needs_extended_stablizers(linked_cubes: tuple[CubeSpec, CubeSpec]) -> bool:
        """Check if the pipe represented by the given ``arms`` and
        ``linked_cubes`` requires extended stablizers.

        In fixed parity convention, spatial cubes change the parity. That is
        why we need stretched stabilizers. By convention, TQEC inserts stretched
        stabilizers only in the UP/DOWN pipes (i.e., in the Y spatial dimension).

        But if 2 spatial cubes are linked by a pipe in the Y dimension, we
        *might* not need to fix the parity with extended stabilizers. We only
        need to use stretched stabilizers when the parity would be wrong, and
        that is only when exactly 1 of the 2 cubes linked by the pipe has pipes
        in both spatial dimensions

        Args:
            arms: arm(s) of the spatial cube(s) linked by the pipe.
            linked_cubes: a tuple ``(u, v)`` where ``u`` and ``v`` are the
                specifications of the two ends of the pipe.

        Returns:
            ``True`` if extended stablizers should be used, ``False`` otherwise.

        """
        return (
            linked_cubes[0].has_spatial_pipe_in_both_dimensions
            ^ linked_cubes[1].has_spatial_pipe_in_both_dimensions
        )

    def _get_up_down_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        arms: SpatialArms,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        if not FixedParityConventionGenerator.pipe_needs_extended_stablizers(linked_cubes):
            # Special case, a little bit simpler, not using extended stabilizers.
            return self._get_up_and_down_spatial_cube_arm_plaquettes(
                spatial_boundary_basis, linked_cubes, is_reversed, reset, measurement
            )
        # General case, need extended stabilizers.
        SBB, OTB = spatial_boundary_basis, spatial_boundary_basis.flipped()
        # EPs: extended plaquettes
        EPs = self.get_extended_plaquettes(reset, measurement, is_reversed)
        # Dictionary that will be filled with plaquettes
        plaquettes: dict[int, Plaquette] = {}
        # Getting the extended plaquettes for the bulk and filling the dictionary
        bulk1 = EPs[OTB if arms == SpatialArms.UP else SBB].bulk
        bulk2 = EPs[SBB if arms == SpatialArms.UP else OTB].bulk
        plaquettes |= {5: bulk1.top, 6: bulk2.top, 7: bulk1.bottom, 8: bulk2.bottom}
        # Getting the extended plaquette, either for the left or the right
        # boundary depending on the spatial arm that is being asked for.
        boundary_collection = EPs[SBB]
        u, v = linked_cubes
        if arms == SpatialArms.UP:
            boundary = (
                boundary_collection.left_with_arm
                if SpatialArms.LEFT in v.spatial_arms
                else boundary_collection.left_without_arm
            )
            plaquettes |= {1: boundary.top, 3: boundary.bottom}
        else:
            boundary = (
                boundary_collection.right_with_arm
                if SpatialArms.RIGHT in u.spatial_arms
                else boundary_collection.right_without_arm
            )
            plaquettes |= {2: boundary.top, 4: boundary.bottom}
        return Plaquettes(
            FrozenDefaultDict(
                plaquettes,
                default_value=self._mapper.get_plaquette(RPNGDescription.empty()),
            )
        )

    def _get_up_and_down_spatial_cube_arm_plaquettes(
        self,
        spatial_boundary_basis: Basis,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        return self._mapper(self._get_up_and_down_spatial_cube_arm_rpng_descriptions)(
            spatial_boundary_basis, linked_cubes, is_reversed, reset, measurement
        )

    def _get_up_and_down_spatial_cube_arm_rpng_descriptions(
        self,
        spatial_boundary_basis: Basis,
        linked_cubes: tuple[CubeSpec, CubeSpec],
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Return the RPNG descriptions to implement a pipe connecting at least
        one spatial cube.

        The pipe implemented by this method links two cubes such as:

        - at least one of the two cube is a spatial cube (both can be),
        - either none of both of the two linked cubes have pipes in both spatial
          dimensions.

        In particular, the following situations can be encountered (list is not
        exhaustive):

        - a straight line ending on a spatial cube, meaning that the pipe links
          a spatial cube with a single arm and a regular cube (case where none
          of the 2 linked cubes have pipes in both spatial dimensions),
        - a "rotated-H" shape (case where both of the 2 linked cubes have pipes
          in both spatial dimensions),
        - ...

        These pipes have in common the fact that they do not require extended
        stabilizers to be implemented.
        """
        # Aliases to shorten line length.
        r, m = reset, measurement
        SBB = spatial_boundary_basis
        # BPs: Bulk Plaquettes.
        BPs_UP = self.get_bulk_rpng_descriptions(is_reversed, r, m, (2, 3))
        BPs_DOWN = self.get_bulk_rpng_descriptions(is_reversed, r, m, (0, 1))
        # CSs: Corner Stabilizers (3-body stabilizers).
        CSs = self.get_3_body_rpng_descriptions(SBB, is_reversed, r, m)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)
        # Here, depending on the linked cubes, we might insert regular two-body
        # plaquettes or three-body plaquettes.
        u, v = linked_cubes
        both_cubes_have_spatial_pipes_in_both_dimensions = (
            u.has_spatial_pipe_in_both_dimensions and v.has_spatial_pipe_in_both_dimensions
        )
        right_plaquette = (
            CSs[3] if SpatialArms.RIGHT in u.spatial_arms else TBPs[SBB][PlaquetteOrientation.RIGHT]
        )
        left_plaquette = (
            CSs[0] if SpatialArms.LEFT in v.spatial_arms else TBPs[SBB][PlaquetteOrientation.LEFT]
        )
        # TLB, OTB: Top-Left Basis, Other Basis
        TLB = SBB if both_cubes_have_spatial_pipes_in_both_dimensions else SBB.flipped()
        OTB = TLB.flipped()
        LEFT, RIGHT = (3, 2) if both_cubes_have_spatial_pipes_in_both_dimensions else (1, 4)
        return FrozenDefaultDict(
            {
                RIGHT: right_plaquette,
                LEFT: left_plaquette,
                5: BPs_UP[TLB][Orientation.VERTICAL],
                6: BPs_UP[OTB][Orientation.HORIZONTAL],
                7: BPs_DOWN[OTB][Orientation.HORIZONTAL],
                8: BPs_DOWN[TLB][Orientation.VERTICAL],
            },
            default_value=RPNGDescription.empty(),
        )

    ############################################################
    #                         Hadamard                         #
    ############################################################

    ########################################
    #           Regular junction           #
    ########################################
    def get_temporal_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.Template` instance
        needed to implement a transversal Hadamard gate applied on one logical
        qubit.
        """
        return QubitTemplate()

    def get_temporal_hadamard_rpng_descriptions(
        self, is_reversed: bool, z_orientation: Orientation = Orientation.HORIZONTAL
    ) -> FrozenDefaultDict[int, RPNGDescription]:
        """Returns a description of the plaquettes needed to implement a
        transversal Hadamard gate applied on one logical qubit.

        Warning:
            This method is tightly coupled with
            :meth:`FixedParityConventionGenerator.get_temporal_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.Template` instance returned by this
            method.

        Arguments:
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        # BPs: Bulk Plaquettes.
        BPs = self.get_bulk_hadamard_rpng_descriptions(is_reversed)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed, hadamard=True)
        HBASIS = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
        VBASIS = HBASIS.flipped()
        return FrozenDefaultDict(
            {
                6: TBPs[VBASIS][PlaquetteOrientation.UP],
                7: TBPs[HBASIS][PlaquetteOrientation.LEFT],
                9: BPs[VBASIS][Orientation.HORIZONTAL],
                10: BPs[HBASIS][Orientation.VERTICAL],
                12: TBPs[HBASIS][PlaquetteOrientation.RIGHT],
                13: TBPs[VBASIS][PlaquetteOrientation.DOWN],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_temporal_hadamard_plaquettes(
        self, is_reversed: bool, z_orientation: Orientation = Orientation.HORIZONTAL
    ) -> Plaquettes:
        return self._mapper(self.get_temporal_hadamard_rpng_descriptions)(
            is_reversed, z_orientation
        )

    ########################################
    #                X pipe                #
    ########################################
    def get_spatial_vertical_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement a spatial Hadamard pipe between two logical
        qubits aligned on the ``X`` axis.
        """
        return QubitVerticalBorders()

    def get_spatial_vertical_hadamard_rpng_descriptions(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
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
            :meth:`FixedParityConventionGenerator.get_spatial_vertical_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            top_left_basis: basis of the top-left-most stabilizer.
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        # BPs: Bulk Plaquettes.
        BPs = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)
        bulk1, bulk2, bottom = self.get_spatial_x_hadamard_rpng_descriptions(
            top_left_basis, is_reversed, reset, measurement
        )
        # tlb: top-left basis, otb: other basis.
        tlb, otb = top_left_basis, top_left_basis.flipped()
        return FrozenDefaultDict(
            {
                2: TBPs[otb][PlaquetteOrientation.UP],
                3: bottom,
                5: bulk1,
                6: bulk2,
                7: BPs[tlb][Orientation.VERTICAL],
                8: BPs[otb][Orientation.HORIZONTAL],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_spatial_vertical_hadamard_plaquettes(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        return self._mapper(self.get_spatial_vertical_hadamard_rpng_descriptions)(
            top_left_basis, is_reversed, reset, measurement
        )

    ########################################
    #                Y pipe                #
    ########################################
    def get_spatial_horizontal_hadamard_raw_template(self) -> RectangularTemplate:
        """Returns the :class:`~tqec.templates.base.RectangularTemplate`
        instance needed to implement a spatial Hadamard pipe between two logical
        qubits aligned on the ``Y`` axis.
        """
        return QubitHorizontalBorders()

    def get_spatial_horizontal_hadamard_rpng_descriptions(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
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
            :meth:`FixedParityConventionGenerator.get_spatial_horizontal_hadamard_raw_template`
            and the returned ``RPNG`` descriptions should only be considered
            valid when used in conjunction with the
            :class:`~tqec.templates.base.RectangularTemplate` instance returned
            by this method.

        Arguments:
            top_left_basis: basis of the top-left-most stabilizer.
            is_reversed: flag indicating if the plaquette schedule should be
                reversed or not. Useful to limit the loss of code distance when
                hook errors are not correctly oriented by alternating regular
                and reversed plaquettes.
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
        # BPs: Bulk Plaquettes.
        BPs = self.get_bulk_rpng_descriptions(is_reversed, reset, measurement)
        # TBPs: Two Body Plaquettes.
        TBPs = self.get_2_body_rpng_descriptions(is_reversed)
        bulk1, bulk2, left = self.get_spatial_y_hadamard_rpng_descriptions(
            top_left_basis, is_reversed, reset, measurement
        )
        # tlb: top-left basis, otb: other basis.
        tlb, otb = top_left_basis, top_left_basis.flipped()
        return FrozenDefaultDict(
            {
                1: left,
                4: TBPs[otb][PlaquetteOrientation.RIGHT],
                5: bulk1,
                6: bulk2,
                7: BPs[otb][Orientation.VERTICAL],
                8: BPs[tlb][Orientation.HORIZONTAL],
            },
            default_value=RPNGDescription.empty(),
        )

    def get_spatial_horizontal_hadamard_plaquettes(
        self,
        top_left_basis: Basis,
        is_reversed: bool,
        reset: Basis | None = None,
        measurement: Basis | None = None,
    ) -> Plaquettes:
        return self._mapper(self.get_spatial_horizontal_hadamard_rpng_descriptions)(
            top_left_basis, is_reversed, reset, measurement
        )
