from tqec.enums import Basis
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.enums import ZObservableOrientation
from tqec.templates.indices.qubit import (
    QubitHorizontalBorders,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def get_memory_qubit_raw_template() -> QubitTemplate:
    """Returns the :class:`~tqec.templates.indices.base.Template` instance
    needed to implement a single logical qubit.

    Returns:
        an instance of :class:`~tqec.templates.indices.qubit.QubitTemplate`.
    """
    return QubitTemplate()


def get_memory_qubit_rpng_descriptions(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
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
        conjunction with the :class:`~tqec.templates.indices.base.Template`
        instance returned by this function.

    Arguments:
        orientation: orientation of the ``Z`` observable. Used to compute the
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
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # bh: basis horizontal, bv: basis vertical
    bh = orientation.horizontal_basis()
    bv = orientation.vertical_basis()

    return FrozenDefaultDict(
        {
            # UP
            6: RPNGDescription.from_string(f"---- ---- {r}{bv}3{m} {r}{bv}4{m}"),
            # LEFT
            7: RPNGDescription.from_string(f"---- {r}{bh}3{m} ---- {r}{bh}4{m}"),
            # Bulk
            9: RPNGDescription.from_string(
                f"{r}{bv}1{m} {r}{bv}2{m} {r}{bv}3{m} {r}{bv}4{m}"
            ),
            10: RPNGDescription.from_string(
                f"{r}{bh}1{m} {r}{bh}3{m} {r}{bh}2{m} {r}{bh}4{m}"
            ),
            # RIGHT
            12: RPNGDescription.from_string(f"{r}{bh}1{m} ---- {r}{bh}2{m} ----"),
            # DOWN
            13: RPNGDescription.from_string(f"{r}{bv}1{m} {r}{bv}2{m} ---- ----"),
        },
        default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
    )


def get_memory_vertical_boundary_raw_template() -> QubitVerticalBorders:
    """Returns the :class:`~tqec.templates.indices.base.Template` instance
    needed to implement a regular spatial pipe between two logical qubits
    aligned on the ``X`` axis.

    Returns:
        an instance of :class:`~tqec.templates.indices.qubit.QubitVerticalBorders`.
    """
    return QubitVerticalBorders()


def get_memory_vertical_boundary_rpng_descriptions(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
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
        conjunction with the :class:`~tqec.templates.indices.base.Template`
        instance returned by this function.

    Arguments:
        orientation: orientation of the ``Z`` observable. Used to compute the
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
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # bh: basis horizontal, bv: basis vertical
    bh = orientation.horizontal_basis()
    bv = orientation.vertical_basis()

    return FrozenDefaultDict(
        {
            # TOP_RIGHT
            2: RPNGDescription.from_string(f"---- ---- {r}{bv}3{m} -{bv}4-"),
            # BOTTOM_LEFT
            3: RPNGDescription.from_string(f"-{bv}1- {r}{bv}2{m} ---- ----"),
            # LEFT bulk
            5: RPNGDescription.from_string(f"-{bv}1- {r}{bv}2{m} -{bv}3- {r}{bv}4{m}"),
            6: RPNGDescription.from_string(f"-{bh}1- {r}{bh}3{m} -{bh}2- {r}{bh}4{m}"),
            # RIGHT bulk
            7: RPNGDescription.from_string(f"{r}{bh}1{m} -{bh}3- {r}{bh}2{m} -{bh}4-"),
            8: RPNGDescription.from_string(f"{r}{bv}1{m} -{bv}2- {r}{bv}3{m} -{bv}4-"),
        },
        default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
    )


def get_memory_horizontal_boundary_raw_template() -> QubitHorizontalBorders:
    """Returns the :class:`~tqec.templates.indices.base.Template` instance
    needed to implement a regular spatial pipe between two logical qubits
    aligned on the ``Y`` axis.

    Returns:
        an instance of :class:`~tqec.templates.indices.qubit.QubitHorizontalBorders`.
    """
    return QubitHorizontalBorders()


def get_memory_horizontal_boundary_rpng_descriptions(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
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
        conjunction with the :class:`~tqec.templates.indices.base.Template`
        instance returned by this function.

    Arguments:
        orientation: orientation of the ``Z`` observable. Used to compute the
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
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # bh: basis horizontal, bv: basis vertical
    bh = orientation.horizontal_basis()
    bv = orientation.vertical_basis()

    return FrozenDefaultDict(
        {
            # TOP_LEFT
            1: RPNGDescription.from_string(f"---- -{bh}3- ---- {r}{bh}4{m}"),
            # BOTTOM_RIGHT
            4: RPNGDescription.from_string(f"{r}{bh}1{m} ---- -{bh}2- ----"),
            # TOP bulk
            5: RPNGDescription.from_string(f"-{bv}1- -{bv}2- {r}{bv}3{m} {r}{bv}4{m}"),
            6: RPNGDescription.from_string(f"-{bh}1- -{bh}3- {r}{bh}2{m} {r}{bh}4{m}"),
            # BOTTOM bulk
            7: RPNGDescription.from_string(f"{r}{bh}1{m} {r}{bh}3{m} -{bh}2- -{bh}4-"),
            8: RPNGDescription.from_string(f"{r}{bv}1{m} {r}{bv}2{m} -{bv}3- -{bv}4-"),
        },
        default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
    )
