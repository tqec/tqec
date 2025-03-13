"""Provide functions building the :class:`~tqec.templates.rpng.RPNGTemplate`
instances representing spatial cubes and arms.

This module provides 2 functions to create
:class:`~tqec.templates.rpng.RPNGTemplate` instances:

- :func:`get_spatial_cube_qubit_template` that creates spatial cubes,
- and :func:`get_spatial_cube_arm_template` that creates the arms.

## Terminology

In this module, a **spatial cube** always refers to the logical qubit that
has all the spatial boundaries in the same basis.

The spatial pipes connected to the spatial cubes are called **arms**.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Final

from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.utils import default_plaquette_mapper
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict


class _Orientation(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()

    def flip(self) -> _Orientation:
        match self:
            case _Orientation.VERTICAL:
                return _Orientation.HORIZONTAL
            case _Orientation.HORIZONTAL:
                return _Orientation.VERTICAL


def _get_bulk_plaquettes(
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> dict[Basis, dict[_Orientation, RPNGDescription]]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    return {
        Basis.X: {
            _Orientation.VERTICAL: RPNGDescription.from_string(
                f"{r}x1{m} {r}x4{m} {r}x3{m} {r}x5{m}"
            ),
            _Orientation.HORIZONTAL: RPNGDescription.from_string(
                f"{r}x1{m} {r}x2{m} {r}x3{m} {r}x5{m}"
            ),
        },
        Basis.Z: {
            _Orientation.VERTICAL: RPNGDescription.from_string(
                f"{r}z1{m} {r}z4{m} {r}z3{m} {r}z5{m}"
            ),
            _Orientation.HORIZONTAL: RPNGDescription.from_string(
                f"{r}z1{m} {r}z2{m} {r}z3{m} {r}z5{m}"
            ),
        },
    }


def _get_3_body_stabilizers(
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> tuple[RPNGDescription, RPNGDescription, RPNGDescription, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # Note: the schedule of CNOT gates in corner plaquettes is less important
    # because hook errors do not exist on 3-body stabilizers. We arbitrarily
    # chose the schedule of the plaquette group the corner belongs to.
    # TODO: we include reset/measurement on every data-qubit at the moment. That
    # was not what was done before. This might have to change.
    return (
        RPNGDescription.from_string(f"---- {r}z4{m} {r}z3{m} {r}z5{m}"),
        RPNGDescription.from_string(f"{r}x1{m} ---- {r}x3{m} {r}x5{m}"),
        RPNGDescription.from_string(f"{r}x1{m} {r}x2{r} ---- {r}x5{r}"),
        RPNGDescription.from_string(f"{r}z1{m} {r}z4{m} {r}z3{m} ----"),
    )


def get_spatial_cube_qubit_raw_template() -> QubitSpatialCubeTemplate:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement a spatial cube.

    Note:
        A spatial cube is defined as a cube with all its spatial boundaries in
        the same basis.
        Such a cube might appear in stability experiments (e.g.,
        http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
        with more than one pipe in the spatial plane) or in other QEC gadgets
        such as the lattice surgery implementation of a ``CZ`` gate.

    Returns:
        an instance of
        :class:`~tqec.templates.qubit.QubitSpatialCubeTemplate`.
    """
    return QubitSpatialCubeTemplate()


def get_spatial_cube_qubit_rpng_descriptions(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    """Returns a description of the plaquettes needed to implement a spatial
    cube.

    Note:
        A spatial cube is defined as a cube with all its spatial boundaries in
        the same basis.
        Such a cube might appear in stability experiments (e.g.,
        http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
        with more than one pipe in the spatial plane) or in other QEC gadgets
        such as the lattice surgery implementation of a ``CZ`` gate.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Warning:
        This function is tightly coupled with
        :func:`get_spatial_cube_qubit_raw_template` and the returned
        ``RPNG`` descriptions should only be considered valid when used in
        conjunction with the :class:`~tqec.templates.base.Template`
        instance returned by this function.

    Warning:
        By convention, this function does not populate the plaquettes on the
        boundaries where an arm is present **BUT** do populate the corners (that
        are part of the boundaries, so this is an exception to the first part of
        the sentence).

        The rationale behind that convention is that the logical qubit
        representing the spatial cube is completely aware of all the arms
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
            of the spatial cube.
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

    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be = basis external
    be = spatial_boundary_basis.value.lower()
    # Get parity information in a more convenient format. Note that if the boundary
    # is composed of Z stabilizers then the horizontal arms are supposed to be
    # in odd-parity. Using two variables for the same quantity to help reading
    # the code.
    horizontal_is_odd = boundary_is_z = spatial_boundary_basis == Basis.Z
    # Pre-define some collection of plaquettes
    # CSs: Corner Stabilizers (3-body stabilizers).
    CSs = _get_3_body_stabilizers(reset, measurement)
    # BPs: Bulk Plaquettes.
    BPs = _get_bulk_plaquettes(reset, measurement)

    mapping: dict[int, RPNGDescription] = {}

    ####################
    #     Corners      #
    ####################
    # Corners might contain a 3-body stabilizer measurement if both arms around
    # are set. The case in which only one of the arm is present (e.g., UP
    # without LEFT for the corner 1) and where a 2-body stabilizer should be
    # inserted instead of a 3-body stabilizer is handled in the next ifs, in the
    # "Boundaries" section.
    # Any given corner (indexed 1, 2, 3 or 4) contains a 3-body stabilizer if
    # and only if all the following points are verified:
    # - the two neighbouring arms are present (i.e., no 3-body stabiliser on the
    #   plaquette indexed 1 if either UP or LEFT is not present in the arms),
    # - and the parity of both arms makes it possible to insert a 3-body
    #   stabilizer without overlapping any 2-body stabilizer on the arm. Note
    #   that the parities of both arms around a corner are necessary different
    #   (if UP is odd, LEFT and RIGHT should be even and DOWN should also be
    #   odd) and so we can summarise that condition as "the horizontal line is
    #   odd (or even) parity".
    # Alias to reduce clutter in the implementation for corners
    SA = SpatialArms
    if SA.UP in arms and SA.LEFT in arms and horizontal_is_odd:
        mapping[1] = CSs[0]
    if SA.UP in arms and SA.RIGHT in arms and not horizontal_is_odd:
        mapping[2] = CSs[1]
    if SA.LEFT in arms and SA.DOWN in arms and not horizontal_is_odd:
        mapping[3] = CSs[2]
    if SA.DOWN in arms and SA.RIGHT in arms and horizontal_is_odd:
        mapping[4] = CSs[3]

    ####################
    #    Boundaries    #
    ####################
    # Fill the boundaries that should be filled in the returned template because
    # they have no arms, and so will not be filled later.
    # Note that indices 1, 2, 3 and 4 **might** be set twice in the 4 ifs below.
    # These cases are handled later in the function and will overwrite the
    # description on 1, 2, 3 or 4 if needed, so we do not have to account for
    # those cases here.
    if SpatialArms.UP not in arms:
        CORNER, BULK = (1, 10) if boundary_is_z else (2, 9)
        mapping[CORNER] = mapping[BULK] = RPNGDescription.from_string(
            f"---- ---- {r}{be}3{m} {r}{be}5{m}"
        )
    if SpatialArms.RIGHT not in arms:
        CORNER, BULK = (4, 21) if boundary_is_z else (2, 22)
        mapping[CORNER] = mapping[BULK] = RPNGDescription.from_string(
            f"{r}{be}1{m} ---- {r}{be}2{m} ----"
        )
    if SpatialArms.DOWN not in arms:
        CORNER, BULK = (4, 23) if boundary_is_z else (3, 24)
        mapping[CORNER] = mapping[BULK] = RPNGDescription.from_string(
            f"{r}{be}1{m} {r}{be}2{m} ---- ----"
        )
    if SpatialArms.LEFT not in arms:
        CORNER, BULK = (1, 12) if boundary_is_z else (3, 11)
        mapping[CORNER] = mapping[BULK] = RPNGDescription.from_string(
            f"---- {r}{be}3{m} ---- {r}{be}4{m}"
        )

    # If we have an L-shaped junction, the opposite corner plaquette should be
    # removed from the mapping (this is the case where it has been set twice in
    # the ifs above).
    if SpatialArms.LEFT not in arms and SpatialArms.UP not in arms and boundary_is_z:
        del mapping[1]
    if (
        SpatialArms.UP not in arms
        and SpatialArms.RIGHT not in arms
        and not boundary_is_z
    ):
        del mapping[2]
    if (
        SpatialArms.DOWN not in arms
        and SpatialArms.LEFT not in arms
        and not boundary_is_z
    ):
        del mapping[3]
    if SpatialArms.RIGHT not in arms and SpatialArms.DOWN not in arms and boundary_is_z:
        del mapping[4]

    ####################
    #       Bulk       #
    ####################
    # Assigning plaquette description to the bulk, considering that the bulk
    # corners (i.e. indices {5, 6, 7, 8}) should be assigned "regular" plaquettes
    # (i.e. 6 and 7 have the same plaquette as 17, 5 has the same plaquette as
    # 13 and 8 has the same plaquette as 15). If these need to be changed, it
    # will be done afterwards.
    # Setting the orientations for Z plaquettes for each of the four portions of
    # the template bulk.
    ZUP = ZDOWN = _Orientation.VERTICAL if boundary_is_z else _Orientation.HORIZONTAL
    ZRIGHT = ZLEFT = ZUP.flip()
    # If the corresponding arm is missing, the Z plaquette hook error orientation
    # should flip to avoid shortcuts due to hook errors.
    ZUP = ZUP if SpatialArms.UP in arms else ZUP.flip()
    ZDOWN = ZDOWN if SpatialArms.DOWN in arms else ZDOWN.flip()
    ZRIGHT = ZRIGHT if SpatialArms.RIGHT in arms else ZRIGHT.flip()
    ZLEFT = ZLEFT if SpatialArms.LEFT in arms else ZLEFT.flip()
    # The X orientations are the opposite of the Z orientation
    XUP, XDOWN, XRIGHT, XLEFT = ZUP.flip(), ZDOWN.flip(), ZRIGHT.flip(), ZLEFT.flip()

    # Setting the Z plaquettes
    mapping[5] = mapping[13] = BPs[Basis.Z][ZUP]
    mapping[8] = mapping[15] = BPs[Basis.Z][ZDOWN]
    mapping[14] = BPs[Basis.Z][ZRIGHT]
    mapping[16] = BPs[Basis.Z][ZLEFT]
    # Setting the X plaquettes
    mapping[20] = BPs[Basis.X][XLEFT]
    mapping[18] = BPs[Basis.X][XRIGHT]
    mapping[6] = mapping[17] = BPs[Basis.X][XUP]
    mapping[7] = mapping[19] = BPs[Basis.X][XDOWN]

    # In the special cases of an L-shaped junction, the opposite corner **within
    # the bulk** should be overwritten to become a 3-body stabilizer measurement.
    if arms == SpatialArms.DOWN | SpatialArms.RIGHT:
        mapping[5] = CSs[0]
    elif arms == SpatialArms.DOWN | SpatialArms.LEFT:
        mapping[6] = CSs[1]
    elif arms == SpatialArms.UP | SpatialArms.RIGHT:
        mapping[7] = CSs[2]
    elif arms == SpatialArms.UP | SpatialArms.LEFT:
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

    return FrozenDefaultDict(
        mapping,
        default_factory=RPNGDescription.empty,
    )


def get_spatial_cube_arm_raw_template(
    arm: SpatialArms,
) -> QubitVerticalBorders | QubitHorizontalBorders:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement the given spatial ``arm``.

    Args:
        arm: specification of the spatial arm we want a template for.

    Raises:
        TQECException: if the provided ``arm`` is not composed of exactly one
            flag (e.g. ``arm == (SpatialArms.UP | SpatialArms.LEFT)`` would
            raise).

    Returns:
        an instance of
        :class:`~tqec.templates.qubit.QubitHorizontalBorders` or
        :class:`~tqec.templates.qubit.QubitVerticalBorders` depending on
        the provided ``arm``.
    """
    if len(arm) != 1:
        raise TQECException(
            f"The 'arm' parameter should contain exactly 1 flag. Got {arm}."
        )

    if arm == SpatialArms.LEFT or arm == SpatialArms.RIGHT:
        return QubitVerticalBorders()
    elif arm == SpatialArms.UP or arm == SpatialArms.DOWN:
        return QubitHorizontalBorders()
    else:
        raise TQECException(f"Unrecognized spatial arm: {arm}.")


def get_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    arm: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    """Returns a description of the plaquettes needed to implement **one** pipe
    connecting to a spatial cube.

    This function returns a RPNGTemplate instance representing the arm of a
    spatial cube. The returned template is carefully crafted to avoid hook errors
    damaging the logical distance.

    Note:
        A spatial cube is defined as a cube with all its spatial boundaries in
        the same basis.
        Such a cube might appear in stability experiments (e.g.,
        http://arxiv.org/abs/2204.13834), in spatial junctions (i.e., a cube
        with more than one pipe in the spatial plane) or in other QEC gadgets
        such as the lattice surgery implementation of a ``CZ`` gate.

    Note:
        this function does not enforce anything on the input values. As such, it
        is possible to generate a description of a round that will both reset and
        measure the data-qubits.

    Warning:
        This function is tightly coupled with
        :func:`get_spatial_cube_arm_raw_template` and the returned
        ``RPNG`` descriptions should only be considered valid when used in
        conjunction with the :class:`~tqec.templates.base.Template`
        instance returned by this function.

    Warning:
        by convention, this function should **not** populate the plaquettes on
        the corners as :func:`get_spatial_cube_qubit_template` should take
        care of that.

    Arguments:
        spatial_boundary_basis: stabilizers that are measured at each boundaries
            of the spatial cube.
        arm: arm of the spatial cube. Should contain exactly **one** of the
            possible arm flags.
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
        a description of the plaquettes needed to implement **one** pipe
        connecting to a spatial cube.
    """
    match arm:
        case SpatialArms.LEFT:
            return _get_left_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, reset, measurement
            )
        case SpatialArms.RIGHT:
            return _get_right_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, reset, measurement
            )
        case SpatialArms.UP:
            return _get_up_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, reset, measurement
            )
        case SpatialArms.DOWN:
            return _get_down_spatial_cube_arm_rpng_descriptions(
                spatial_boundary_basis, reset, measurement
            )
        case _:
            raise TQECException(
                f"The 'arm' parameter should contain exactly 1 flag. Got {arm}."
            )


def _get_left_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis.value.lower()
    bi = spatial_boundary_basis.flipped().value.lower()

    return FrozenDefaultDict(
        {
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
        },
        default_factory=RPNGDescription.empty,
    )


def _get_right_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis.value.lower()
    bi = spatial_boundary_basis.flipped().value.lower()

    return FrozenDefaultDict(
        {
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
        },
        default_factory=RPNGDescription.empty,
    )


def _get_up_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis.value.lower()
    bi = spatial_boundary_basis.flipped().value.lower()

    return FrozenDefaultDict(
        {
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
        },
        default_factory=RPNGDescription.empty,
    )


def _get_down_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # r/m: reset/measurement basis applied to each data-qubit
    r = reset.value.lower() if reset is not None else "-"
    m = measurement.value.lower() if measurement is not None else "-"
    # be/bi = basis external/basis internal
    be = spatial_boundary_basis.value.lower()
    bi = spatial_boundary_basis.flipped().value.lower()

    return FrozenDefaultDict(
        {
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
        },
        default_factory=RPNGDescription.empty,
    )


get_spatial_cube_qubit_plaquettes: Final = default_plaquette_mapper(
    get_spatial_cube_qubit_rpng_descriptions
)
get_spatial_cube_arm_plaquettes: Final = default_plaquette_mapper(
    get_spatial_cube_arm_rpng_descriptions
)
