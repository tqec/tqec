"""Provide functions building the :class:`~tqec.templates.rpng.RPNGTemplate`
instances representing spatial junctions and arms.

This module provides 2 functions to create
:class:`~tqec.templates.rpng.RPNGTemplate` instances:

- :func:`get_spatial_junction_qubit_template` that creates spatial junctions,
- and :func:`get_spatial_junction_arm_template` that creates the arms.

## Terminology

In this module, a **spatial junction** always refers to the logical qubit that
has at least 2 pipes in the spatial plane (``X`` or ``Y`` axis).

The pipes connected to the spatial junction are called **arms**.
"""

from typing import Literal

from tqec.compile.specs.enums import JunctionArms
from tqec.exceptions import TQECException
from tqec.plaquette.enums import Basis
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.indices.qubit import (
    QubitHorizontalBorders,
    QubitSpatialJunctionTemplate,
    QubitVerticalBorders,
)
from tqec.templates.rpng import RPNGTemplate


def get_spatial_junction_qubit_template(
    spatial_boundary_basis: Literal["x", "z"],
    arms: JunctionArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    """Implementation of a logical qubit acting as a spatial junction.

    This function returns a RPNGTemplate instance representing a logical qubit
    connecting to others in space and forming a spatial junction. The returned
    template is carefully crafted to avoid hook errors damaging the logical
    distance.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Warning:
        By convention, this function does not populate the plaquettes on the
        boundaries where an arm is present **BUT** do populate the corners (that
        are part of the boundaries, so this is an exception to the first part of
        the sentence).

        The rationale behind that convention is that the logical qubit
        representing the spatial junction is completely aware of all the arms
        that should be implemented whereas each arm in isolation does not know
        if the other arms are present or not. That means that corners, whose
        plaquette depends on the presence or absence of the two arms it belongs
        to, require information that is given to this function, but not to the
        arm-generation function.

        Arms should follow that convention and should not replace the plaquette
        descriptions on the corners (i.e., not include an explicit mapping, even
        to the empty plaquette, from the index of the corner to a plaquette).


    Arguments:
        spatial_boundary_basis: stabilizers that are measured at each boundaries
            of the spatial junction.
        arms: flag-like enumeration listing the arms that are used around the
            logical qubit. The returned template will be adapted to be
            compatible with such a layout.
        reset: basis of the reset operation performed on data-qubits. Defaults
            to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on data-qubits.
            Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.

    Raises:
        TQECException: if ``arms`` only contains 0 or 1 flag.
        TQECException: if ``arms`` describes an I-shaped junction (TOP/DOWN or
            LEFT/RIGHT).

    Returns:
        a description of a logical qubit performing a memory operation while
        being enclosed by 2 or more arms.
    """
    # In this function implementation, all the indices used are referring to the
    # indices returned by the QubitSpatialJunctionTemplate template. They are
    # copied below for convenience, but the only source of truth is in the
    # QubitSpatialJunctionTemplate docstring!
    #      1   9  10   9  10   9  10   9  10   2
    #     11   5  17  13  17  13  17  13   6  18
    #     12  17  13  17  13  17  13  17  14  19
    #     11  16  17  13  17  13  17  14  17  18
    #     12  17  16  17  13  17  14  17  14  19
    #     11  16  17  16  17  15  17  14  17  18
    #     12  17  16  17  15  17  15  17  14  19
    #     11  16  17  15  17  15  17  15  17  18
    #     12   7  15  17  15  17  15  17   8  19
    #      3  20  21  20  21  20  21  20  21   4

    if len(arms) < 2:
        raise TQECException(
            f"Expected two or more arms. Got {arms} that contains {len(arms)} arm."
        )
    if arms in JunctionArms.I_shaped_arms():
        raise TQECException(
            "I-shaped spatial junctions (i.e., spatial junctions with only two "
            "arms that are the opposite of each other: LEFT/RIGHT or UP/DOWN) "
            "should not use get_spatial_junction_qubit_template but rather use "
            "a conventional memory logical qubit with get_memory_qubit_template."
        )

    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis
    bi = "x" if spatial_boundary_basis == "z" else "z"

    mapping: dict[int, RPNGDescription] = {}
    ####################
    #     Corners      #
    ####################
    # Corners 2 and 3 are always empty, but corners 1 and 4 might contain a 3-body
    # stabilizer measurement if both arms around are set. The case in which only
    # one of the arm is present (e.g., UP without LEFT) and where a 2-body
    # stabilizer should be inserted instead of a 3-body stabilizer is handled
    # in the next ifs, in the "Boundaries" section.
    if JunctionArms.UP in arms and JunctionArms.LEFT in arms:
        mapping[1] = RPNGDescription.from_string(f"---- {r}{be}3{m} -{be}4- -{be}5-")
    if JunctionArms.DOWN in arms and JunctionArms.RIGHT in arms:
        mapping[4] = RPNGDescription.from_string(
            f"{r}{be}1{m} {r}{be}2{m} -{be}4- ----"
        )

    ####################
    #    Boundaries    #
    ####################
    # Fill the boundaries that should be filled in the returned template because
    # they have no junction, and so will not be filled later.
    # Note that indices 1 and 4 **might** be set twice in the 4 ifs below. These
    # cases are handled later in the function and will overwrite the description
    # on 1 and 4 if needed, so we do not have to account for those cases here.
    if JunctionArms.UP not in arms:
        mapping[1] = mapping[10] = RPNGDescription.from_string(
            f"---- ---- {r}{be}3{m} {r}{be}4{m}"
        )
    if JunctionArms.RIGHT not in arms:
        mapping[4] = mapping[18] = RPNGDescription.from_string(
            f"{r}{be}1{m} ---- {r}{be}2{m} ----"
        )
    if JunctionArms.DOWN not in arms:
        mapping[4] = mapping[20] = RPNGDescription.from_string(
            f"{r}{be}1{m} {r}{be}2{m} ---- ----"
        )
    if JunctionArms.LEFT not in arms:
        mapping[1] = mapping[12] = RPNGDescription.from_string(
            f"---- {r}{be}3{m} ---- {r}{be}4{m}"
        )

    # If we have a down-right or top-left L-shaped junction, the opposite corner
    # plaquette should be removed from the mapping (this is the case where it
    # has been set twice in the ifs above).
    if arms == JunctionArms.UP | JunctionArms.LEFT:
        del mapping[4]
    elif arms == JunctionArms.DOWN | JunctionArms.RIGHT:
        del mapping[1]

    ####################
    #       Bulk       #
    ####################
    # Assigning plaquette description to the bulk, considering that the bulk
    # corners (i.e. indices {5, 6, 7, 8}) should be assigned "regular" plaquettes
    # (i.e. 6 and 7 have the same plaquette as 17, 5 has the same plaquette as
    # 13 and 8 has the same plaquette as 15). If these need to be changed, it
    # will be done afterwards.
    internal_basis_plaquette = RPNGDescription.from_string(
        f"{r}{bi}1{m} {r}{bi}3{m} {r}{bi}2{m} {r}{bi}5{m}"
    )
    mapping[6] = mapping[7] = mapping[17] = internal_basis_plaquette

    # be{h,v}hp: basis external {horizontal,vertical} hook plaquette
    behhp = RPNGDescription.from_string(
        f"{r}{be}1{m} {r}{be}2{m} {r}{be}3{m} {r}{be}4{m}"
    )
    bevhp = RPNGDescription.from_string(
        f"{r}{be}1{m} {r}{be}4{m} {r}{be}3{m} {r}{be}5{m}"
    )
    mapping[5] = mapping[13] = bevhp if JunctionArms.UP in arms else behhp
    mapping[14] = behhp if JunctionArms.RIGHT in arms else bevhp
    mapping[8] = mapping[15] = bevhp if JunctionArms.DOWN in arms else behhp
    mapping[16] = behhp if JunctionArms.LEFT in arms else bevhp

    # In the special cases of an L-shaped junction TOP/LEFT or DOWN/RIGHT, the
    # opposite corner **within the bulk** should be overwritten to become a
    # 3-body stabilizer measurement.
    if arms == JunctionArms.UP | JunctionArms.LEFT:
        mapping[8] = RPNGDescription.from_string(
            f"{r}{be}1{m} {r}{be}2{m} {r}{be}4{m} ----"
        )
    elif arms == JunctionArms.DOWN | JunctionArms.RIGHT:
        mapping[5] = RPNGDescription.from_string(
            f"---- {r}{be}2{m} {r}{be}4{m} {r}{be}5{m}"
        )

    ####################
    #  Sanity checks   #
    ####################
    # All the plaquettes in the bulk should be set.
    bulk_plaquette_indices = {5, 6, 7, 8, 13, 14, 15, 16, 17}
    missing_bulk_plaquette_indices = bulk_plaquette_indices - mapping.keys()
    assert not missing_bulk_plaquette_indices, (
        "Some plaquette(s) in the bulk were not correctly assigned to a "
        f"RPNGDescription. Missing indices: {missing_bulk_plaquette_indices}."
    )

    return RPNGTemplate(
        template=QubitSpatialJunctionTemplate(),
        mapping=FrozenDefaultDict(
            mapping,
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def get_spatial_junction_arm_template(
    spatial_boundary_basis: Literal["x", "z"],
    arm: JunctionArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    """Implementation of arms for a spatial junction around a logical qubit.

    This function returns a RPNGTemplate instance representing the arms
    required to perform a spatial junction on a logical qubit that has 2 or more
    arms. The returned template is carefully crafted to avoid hook errors
    damaging the logical distance.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Warning:
        by convention, this function should **not** populate the plaquettes on
        the corners as :func:`get_spatial_junction_qubit_template` should take
        care of that.

    Warning:
        Using this function without :func:`get_spatial_junction_qubit_template`
        is very likely a programming error. Please double-check what you are
        doing if that is your case, in particular how the plaquettes on each
        corner of the center logical qubit are set.

    Arguments:
        spatial_boundary_basis: stabilizers that are measured at each boundaries
            of the spatial junction.
        arm: arm to return a spatial junction for. Should contain exactly
            **one** of the possible arm flags.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Raises:
        TQECException: if ``arm`` does not contain exactly 1 flag (i.e., if it
            contains 0 or 2+ flags).

    Returns:
        a description of the provided ``arm``.
    """
    match arm:
        case JunctionArms.LEFT:
            return _get_left_spatial_junction_arm(
                spatial_boundary_basis, reset, measurement
            )
        case JunctionArms.RIGHT:
            return _get_right_spatial_junction_arm(
                spatial_boundary_basis, reset, measurement
            )
        case JunctionArms.UP:
            return _get_up_spatial_junction_arm(
                spatial_boundary_basis, reset, measurement
            )
        case JunctionArms.DOWN:
            return _get_down_spatial_junction_arm(
                spatial_boundary_basis, reset, measurement
            )
        case _:
            raise TQECException(
                f"The 'arm' parameter should contain exactly 1 flag. Got {arm}."
            )


def _get_left_spatial_junction_arm(
    spatial_boundary_basis: Literal["x", "z"],
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis
    bi = "x" if spatial_boundary_basis == "z" else "z"

    mapping = {
        # TOP_RIGHT: NOT included to avoid overwriting the corner
        # 2: RPNGDescription.from_string(f"---- {r}{be}3{m} -{be}4- -{be}5-"),
        # BOTTOM_LEFT
        3: RPNGDescription.from_string(f"-{be}1- {r}{be}2{m} ---- ----"),
        # LEFT bulk
        5: RPNGDescription.from_string(f"-{be}1- {r}{be}2{m} -{be}3- {r}{be}4{m}"),
        6: RPNGDescription.from_string(f"-{bi}1- {r}{bi}3{m} -{bi}2- {r}{bi}4{m}"),
        # RIGHT bulk
        7: RPNGDescription.from_string(f"{r}{bi}1{m} -{bi}3- {r}{bi}2{m} -{bi}4-"),
        8: RPNGDescription.from_string(f"{r}{be}1{m} -{be}2- {r}{be}3{m} -{be}4-"),
    }
    return RPNGTemplate(
        template=QubitVerticalBorders(),
        mapping=FrozenDefaultDict(
            mapping,
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def _get_right_spatial_junction_arm(
    spatial_boundary_basis: Literal["x", "z"],
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis
    bi = "x" if spatial_boundary_basis == "z" else "z"

    mapping = {
        # TOP_RIGHT
        2: RPNGDescription.from_string(f"---- ---- {r}{be}3{m} -{be}4-"),
        # BOTTOM_LEFT: NOT included to avoid overwriting the corner
        # 3: RPNGDescription.from_string(f"-{be}1- -{be}2- {r}{be}4{m} ----"),
        # LEFT bulk
        5: RPNGDescription.from_string(f"-{be}1- {r}{be}2{m} -{be}3- {r}{be}4{m}"),
        6: RPNGDescription.from_string(f"-{bi}1- {r}{bi}3{m} -{bi}2- {r}{bi}4{m}"),
        # RIGHT bulk
        7: RPNGDescription.from_string(f"{r}{bi}1{m} -{bi}3- {r}{bi}2{m} -{bi}4-"),
        8: RPNGDescription.from_string(f"{r}{be}1{m} -{be}2- {r}{be}3{m} -{be}4-"),
    }
    return RPNGTemplate(
        template=QubitVerticalBorders(),
        mapping=FrozenDefaultDict(
            mapping,
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def _get_up_spatial_junction_arm(
    spatial_boundary_basis: Literal["x", "z"],
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis
    bi = "x" if spatial_boundary_basis == "z" else "z"

    mapping = {
        # TOP_LEFT
        1: RPNGDescription.from_string(f"---- -{be}3- ---- {r}{be}5{m}"),
        # BOTTOM_LEFT: NOT included to avoid overwriting the corner
        # 3: RPNGDescription.from_string(f"---- {r}{be}3{m} -{be}4- -{be}5-"),
        # TOP bulk
        5: RPNGDescription.from_string(f"-{bi}1- -{bi}2- {r}{bi}4{m} {r}{bi}5{m}"),
        6: RPNGDescription.from_string(f"-{be}1- -{be}3- {r}{be}2{m} {r}{be}5{m}"),
        # BOTTOM bulk
        7: RPNGDescription.from_string(f"{r}{bi}1{m} {r}{bi}3{m} -{bi}4- -{bi}5-"),
        8: RPNGDescription.from_string(f"{r}{be}1{m} {r}{be}3{m} -{be}2- -{be}5-"),
    }
    return RPNGTemplate(
        template=QubitHorizontalBorders(),
        mapping=FrozenDefaultDict(
            mapping,
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )


def _get_down_spatial_junction_arm(
    spatial_boundary_basis: Literal["x", "z"],
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> RPNGTemplate:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis
    bi = "x" if spatial_boundary_basis == "z" else "z"

    mapping = {
        # TOP_RIGHT: NOT included to avoid overwriting the corner
        # 1: RPNGDescription.from_string(f"-{be}1- -{be}2- {r}{be}4{m} ----"),
        # BOTTOM_RIGHT
        3: RPNGDescription.from_string(f"{r}{be}1{m} ---- -{be}2- ----"),
        # TOP bulk
        5: RPNGDescription.from_string(f"-{be}1- -{be}4- {r}{be}2{m} {r}{be}5{m}"),
        6: RPNGDescription.from_string(f"-{bi}1- -{bi}3- {r}{bi}4{m} {r}{bi}5{m}"),
        # BOTTOM bulk
        7: RPNGDescription.from_string(f"{r}{be}1{m} {r}{be}3{m} -{be}2- -{be}5-"),
        8: RPNGDescription.from_string(f"{r}{bi}1{m} {r}{bi}3{m} -{bi}4- -{bi}5-"),
    }
    return RPNGTemplate(
        template=QubitHorizontalBorders(),
        mapping=FrozenDefaultDict(
            mapping,
            default_factory=lambda: RPNGDescription.from_string("---- ---- ---- ----"),
        ),
    )
