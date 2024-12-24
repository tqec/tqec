from typing import Literal

from tqec.plaquette.enums import MeasurementBasis, ResetBasis
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.enums import ZObservableOrientation
from tqec.templates.indices.qubit import (
    QubitHorizontalBorders,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.templates.rpng import RPNGTemplate


def get_temporal_hadamard_template(
    orientation: ZObservableOrientation = ZObservableOrientation.HORIZONTAL,
) -> RPNGTemplate:
    """Returns a representation of a transversal Hadamard gate applied on one
    logical qubit.

    This function returns a RPNGTemplate instance that performs a transversal
    Hadamard gate. It is basically performing a standard memory operation, but
    also include a Hadamard gate on each data-qubit, effectively performing a
    fault-tolerant Hadamard gate by transversal application of physical gates.

    Arguments:
        orientation: orientation of the Z observable. Used to compute the
            stabilizers that should be measured on the boundaries and in the
            bulk of the returned logical qubit description.

    Returns:
        an implementation of transversal Hadamard gate.
    """
    bh = orientation.horizontal_basis()
    bv = orientation.vertical_basis()

    return RPNGTemplate(
        template=QubitTemplate(),
        mapping=FrozenDefaultDict(
            {
                # UP
                6: RPNGDescription.from_string(f"---- ---- -{bv}3h -{bv}4h"),
                # LEFT
                7: RPNGDescription.from_string(f"---- -{bh}3h ---- -{bh}4h"),
                # BULK_1
                9: RPNGDescription.from_string(f"-{bv}1h -{bv}2h -{bv}3h -{bv}4h"),
                # BULK_2
                10: RPNGDescription.from_string(f"-{bh}1h -{bh}3h -{bh}2h -{bh}4h"),
                # RIGHT
                12: RPNGDescription.from_string(f"-{bh}1h ---- -{bh}2h ----"),
                # DOWN
                13: RPNGDescription.from_string(f"-{bv}1h -{bv}2h ---- ----"),
            },
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def get_spatial_horizontal_hadamard_template(
    top_left_is_z_stabilizer: bool,
    reset: ResetBasis | None = None,
    measurement: MeasurementBasis | None = None,
) -> RPNGTemplate:
    """Returns a representation of a "transversal" Hadamard gate at the interface
    between two logical qubits aligned on the Y-axis

    Note:
        by convention, the hadamard-like transition is performed at the top-most
        plaquettes.

    Arguments:
        top_left_is_z_stabilizer: if ``True``, the plaquette with index 5 in
            :class:`~tqec.templates.indices.qubit.QubitHorizontalBorders`
            should be measuring a Z stabilizer on its 2 top-most data-qubits and
            a X stabilizer on its 2 bottom-most data-qubits. Else, it measures a
            X stabilizer on its two top-most data-qubits and a Z stabilizer on
            its two bottom-most data-qubits.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Returns:
        a description of a junction in the Y-axis and performing a logical
        Hadamard operation.
    """
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # b1: basis of top-left data-qubit, b2: the other basis
    b1: Literal["x", "z"] = "z" if top_left_is_z_stabilizer else "x"
    b2: Literal["x", "z"] = "x" if top_left_is_z_stabilizer else "z"

    return RPNGTemplate(
        template=QubitHorizontalBorders(),
        mapping=FrozenDefaultDict(
            {
                # TOP_LEFT, where the Hadamard transition occurs
                1: RPNGDescription.from_string(f"---- -{b2}3- ---- {r}{b1}4{m}"),
                # BOTTOM_RIGHT, normal plaquette
                4: RPNGDescription.from_string(f"{r}{b1}1{m} ---- -{b1}2- ----"),
                # TOP bulk, where the Hadamard transition occurs
                5: RPNGDescription.from_string(
                    f"-{b1}1- -{b1}2- {r}{b2}3{m} {r}{b2}4{m}"
                ),
                6: RPNGDescription.from_string(
                    f"-{b2}1- -{b2}3- {r}{b1}2{m} {r}{b1}4{m}"
                ),
                # BOTTOM bulk, normal plaquettes
                7: RPNGDescription.from_string(
                    f"{r}{b1}1{m} {r}{b1}3{m} -{b1}2- -{b1}4-"
                ),
                8: RPNGDescription.from_string(
                    f"{r}{b2}1{m} {r}{b2}2{m} -{b2}3- -{b2}4-"
                ),
            },
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def get_spatial_vertical_hadamard_template(
    top_left_is_z_stabilizer: bool,
    reset: ResetBasis | None = None,
    measurement: MeasurementBasis | None = None,
) -> RPNGTemplate:
    """Returns a representation of a "transversal" Hadamard gate at the interface
    between two logical qubits aligned on the X-axis.

    Note:
        by convention, the hadamard-like transition is performed at the left-most
        plaquettes.

    Arguments:
        top_left_is_z_stabilizer: if ``True``, the plaquette with index 5 in
            :class:`~tqec.templates.indices.qubit.QubitVerticalBorders`
            should be measuring a Z stabilizer on its 2 left-most data-qubits
            and a X stabilizer on its 2 right-most data-qubits. Else, it
            measures a X stabilizer on its two left-most data-qubits and a Z
            stabilizer on its two right-most data-qubits.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Returns:
        a description of a junction in the X-axis and performing a logical
        Hadamard operation.
    """
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # b1: basis of top-left data-qubit, b2: the other basis
    b1: Literal["x", "z"] = "z" if top_left_is_z_stabilizer else "x"
    b2: Literal["x", "z"] = "x" if top_left_is_z_stabilizer else "z"

    return RPNGTemplate(
        template=QubitVerticalBorders(),
        mapping=FrozenDefaultDict(
            {
                # TOP_RIGHT, normal plaquette
                2: RPNGDescription.from_string(f"---- ---- {r}{b2}3{m} -{b2}4-"),
                # BOTTOM_LEFT, where the Hadamard transition occurs
                3: RPNGDescription.from_string(f"-{b1}1- {r}{b2}2{m} ---- ----"),
                # LEFT bulk, where the Hadamard transition occurs
                5: RPNGDescription.from_string(
                    f"-{b1}1- {r}{b2}2{m} -{b1}3- {r}{b2}4{m}"
                ),
                6: RPNGDescription.from_string(
                    f"-{b2}1- {r}{b1}3{m} -{b2}2- {r}{b1}4{m}"
                ),
                # RIGHT bulk, normal plaquettes
                7: RPNGDescription.from_string(
                    f"{r}{b1}1{m} -{b1}3- {r}{b1}2{m} -{b1}4-"
                ),
                8: RPNGDescription.from_string(
                    f"{r}{b2}1{m} -{b2}2- {r}{b2}3{m} -{b2}4-"
                ),
            },
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )
