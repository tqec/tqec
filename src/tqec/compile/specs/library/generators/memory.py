from typing import Final

from tqec.compile.specs.library.generators._plaquettes import (
    get_2_body_plaquettes,
    get_bulk_plaquettes,
)
from tqec.compile.specs.library.generators.utils import default_plaquette_mapper
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def get_memory_qubit_raw_template() -> QubitTemplate:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement a single logical qubit.

    Returns:
        an instance of :class:`~tqec.templates.qubit.QubitTemplate`.
    """
    return QubitTemplate()


def get_memory_qubit_rpng_descriptions(
    z_orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    """Returns a description of the plaquettes needed to implement a standard
    memory operation on a logical qubit.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Warning:
        This function is tightly coupled with
        :func:`get_memory_qubit_raw_template` and the returned
        ``RPNG`` descriptions should only be considered valid when used in
        conjunction with the :class:`~tqec.templates.base.Template`
        instance returned by this function.

    Arguments:
        z_orientation: orientation of the ``Z`` observable. Used to compute the
            stabilizers that should be measured on the boundaries and in the
            bulk of the returned logical qubit description.
        reset: basis of the reset operation performed on data-qubits. Defaults
            to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on data-qubits.
            Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.

    Returns:
        a description of the plaquettes needed to implement a standard
        memory operation on a logical qubit, optionally with resets or
        measurements on the data-qubits too.
    """
    # Border plaquette indices
    UP, DOWN, LEFT, RIGHT = (
        (6, 13, 7, 12) if z_orientation == Orientation.VERTICAL else (5, 14, 8, 11)
    )
    # Basis for top/bottom and left/right boundary plaquettes
    HBASIS = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
    VBASIS = HBASIS.flipped()
    # Hook errors orientations
    ZHOOK = z_orientation.flip()
    XHOOK = ZHOOK.flip()
    # BPs: Bulk Plaquettes.
    BPs = get_bulk_plaquettes(reset, measurement)
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)

    return FrozenDefaultDict(
        {
            UP: TBPs[VBASIS][PlaquetteOrientation.UP],
            LEFT: TBPs[HBASIS][PlaquetteOrientation.LEFT],
            # Bulk
            9: BPs[Basis.Z][ZHOOK],
            10: BPs[Basis.X][XHOOK],
            RIGHT: TBPs[HBASIS][PlaquetteOrientation.RIGHT],
            DOWN: TBPs[VBASIS][PlaquetteOrientation.DOWN],
        },
        default_factory=RPNGDescription.empty,
    )


def get_memory_vertical_boundary_raw_template() -> QubitVerticalBorders:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement a regular spatial pipe between two logical qubits
    aligned on the ``X`` axis.

    Returns:
        an instance of :class:`~tqec.templates.qubit.QubitVerticalBorders`.
    """
    return QubitVerticalBorders()


def get_memory_vertical_boundary_rpng_descriptions(
    z_orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    """Returns a description of the plaquettes needed to implement a standard
    memory operation on a pipe between two neighbouring logical qubits aligned
    on the ``X``-axis.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Note:
        if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
        measurement) operation in the provided basis will be inserted **only on
        internal data-qubits**. Here, internal data-qubits are all the qubits
        that are in the middle of the template.

    Warning:
        This function is tightly coupled with
        :func:`get_memory_vertical_boundary_raw_template` and the returned
        ``RPNG`` descriptions should only be considered valid when used in
        conjunction with the :class:`~tqec.templates.base.Template`
        instance returned by this function.

    Arguments:
        z_orientation: orientation of the ``Z`` observable. Used to compute the
            stabilizers that should be measured on the boundaries and in the
            bulk of the returned memory description.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Returns:
        a description of the plaquettes needed to implement a standard memory
        operation on a pipe between two neighbouring logical qubits aligned on
        the ``X``-axis, optionally with resets or measurements on the
        data-qubits too.
    """
    # Border plaquette indices
    UP, DOWN = (2, 3) if z_orientation == Orientation.VERTICAL else (1, 4)
    # Basis for top/bottom boundary plaquettes
    VBASIS = Basis.Z if z_orientation == Orientation.VERTICAL else Basis.X
    # Hook errors orientations
    ZHOOK = z_orientation.flip()
    XHOOK = ZHOOK.flip()
    # BPs: Bulk Plaquettes.
    BPs_LEFT = get_bulk_plaquettes(reset, measurement, (1, 3))
    BPs_RIGHT = get_bulk_plaquettes(reset, measurement, (0, 2))
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)

    return FrozenDefaultDict(
        {
            UP: TBPs[VBASIS][PlaquetteOrientation.UP],
            DOWN: TBPs[VBASIS][PlaquetteOrientation.DOWN],
            # LEFT bulk
            5: BPs_LEFT[Basis.Z][ZHOOK],
            6: BPs_LEFT[Basis.X][XHOOK],
            # RIGHT bulk
            7: BPs_RIGHT[Basis.X][XHOOK],
            8: BPs_RIGHT[Basis.Z][ZHOOK],
        },
        default_factory=RPNGDescription.empty,
    )


def get_memory_horizontal_boundary_raw_template() -> QubitHorizontalBorders:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement a regular spatial pipe between two logical qubits
    aligned on the ``Y`` axis.

    Returns:
        an instance of :class:`~tqec.templates.qubit.QubitHorizontalBorders`.
    """
    return QubitHorizontalBorders()


def get_memory_horizontal_boundary_rpng_descriptions(
    z_orientation: Orientation = Orientation.HORIZONTAL,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    """Returns a description of the plaquettes needed to implement a standard
    memory operation on a pipe between two neighbouring logical qubits aligned
    on the ``Y``-axis.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Note:
        if ``reset`` (resp. ``measurement``) is not ``None``, a reset (resp.
        measurement) operation in the provided basis will be inserted **only on
        internal data-qubits**. Here, internal data-qubits are all the qubits
        that are in the middle of the template.

    Warning:
        This function is tightly coupled with
        :func:`get_memory_horizontal_boundary_raw_template` and the returned
        ``RPNG`` descriptions should only be considered valid when used in
        conjunction with the :class:`~tqec.templates.base.Template`
        instance returned by this function.

    Arguments:
        z_orientation: orientation of the ``Z`` observable. Used to compute the
            stabilizers that should be measured on the boundaries and in the
            bulk of the returned memory description.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Returns:
        a description of the plaquettes needed to implement a standard memory
        operation on a pipe between two neighbouring logical qubits aligned on
        the ``Y``-axis, optionally with resets or measurements on the
        data-qubits too.
    """
    # Border plaquette indices
    LEFT, RIGHT = (1, 4) if z_orientation == Orientation.VERTICAL else (3, 2)
    # Basis for left/right boundary plaquettes
    HBASIS = Basis.Z if z_orientation == Orientation.HORIZONTAL else Basis.X
    # Hook errors orientations
    ZHOOK = z_orientation.flip()
    XHOOK = ZHOOK.flip()
    # BPs: Bulk Plaquettes.
    BPs_UP = get_bulk_plaquettes(reset, measurement, (2, 3))
    BPs_DOWN = get_bulk_plaquettes(reset, measurement, (0, 1))
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)

    return FrozenDefaultDict(
        {
            LEFT: TBPs[HBASIS][PlaquetteOrientation.LEFT],
            RIGHT: TBPs[HBASIS][PlaquetteOrientation.RIGHT],
            # TOP bulk
            5: BPs_UP[Basis.Z][ZHOOK],
            6: BPs_UP[Basis.X][XHOOK],
            # BOTTOM bulk
            7: BPs_DOWN[Basis.X][XHOOK],
            8: BPs_DOWN[Basis.Z][ZHOOK],
        },
        default_factory=RPNGDescription.empty,
    )


get_memory_qubit_plaquettes: Final = default_plaquette_mapper(
    get_memory_qubit_rpng_descriptions
)
get_memory_vertical_boundary_plaquettes: Final = default_plaquette_mapper(
    get_memory_vertical_boundary_rpng_descriptions
)
get_memory_horizontal_boundary_plaquettes: Final = default_plaquette_mapper(
    get_memory_horizontal_boundary_rpng_descriptions
)
