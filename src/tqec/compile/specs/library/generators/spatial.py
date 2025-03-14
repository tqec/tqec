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

from typing import Final

from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators._plaquettes import (
    get_2_body_plaquettes,
    get_3_body_plaquettes,
    get_bulk_plaquettes,
)
from tqec.compile.specs.library.generators.utils import default_plaquette_mapper
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitVerticalBorders,
)
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict


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
    # Get parity information in a more convenient format. Note that if the boundary
    # is composed of Z stabilizers then the horizontal arms are supposed to be
    # in even-parity. Using two variables for the same quantity to help reading
    # the code.
    horizontal_is_even = boundary_is_z = spatial_boundary_basis == Basis.Z
    # Pre-define some collection of plaquettes
    # CSs: Corner Stabilizers (3-body stabilizers).
    CSs = get_3_body_plaquettes(reset, measurement)
    # BPs: Bulk Plaquettes.
    BPs = get_bulk_plaquettes(reset, measurement)

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
    if SA.UP in arms and SA.LEFT in arms and horizontal_is_even:
        mapping[1] = CSs[0]
    if SA.UP in arms and SA.RIGHT in arms and not horizontal_is_even:
        mapping[2] = CSs[1]
    if SA.LEFT in arms and SA.DOWN in arms and not horizontal_is_even:
        mapping[3] = CSs[2]
    if SA.DOWN in arms and SA.RIGHT in arms and horizontal_is_even:
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
    # Note that resets and measurements are included on all data-qubits here.
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)
    # SBS: Spatial Boundary Basis.
    SBS = spatial_boundary_basis
    if SpatialArms.UP not in arms:
        CORNER, BULK = (1, 10) if boundary_is_z else (2, 9)
        mapping[CORNER] = mapping[BULK] = TBPs[SBS][PlaquetteOrientation.UP]
    if SpatialArms.RIGHT not in arms:
        CORNER, BULK = (4, 21) if boundary_is_z else (2, 22)
        mapping[CORNER] = mapping[BULK] = TBPs[SBS][PlaquetteOrientation.RIGHT]
    if SpatialArms.DOWN not in arms:
        CORNER, BULK = (4, 23) if boundary_is_z else (3, 24)
        mapping[CORNER] = mapping[BULK] = TBPs[SBS][PlaquetteOrientation.DOWN]
    if SpatialArms.LEFT not in arms:
        CORNER, BULK = (1, 12) if boundary_is_z else (3, 11)
        mapping[CORNER] = mapping[BULK] = TBPs[SBS][PlaquetteOrientation.LEFT]

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
    # (i.e. 6 is assigned the same plaquette as 17, 7 -> 19, 5 -> 13, 8 -> 15).
    # If these need to be changed, it will be done afterwards.
    # Setting the orientations for Z plaquettes for each of the four portions of
    # the template bulk.
    ZUP = ZDOWN = Orientation.VERTICAL if boundary_is_z else Orientation.HORIZONTAL
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
    mapping[6] = mapping[17] = BPs[Basis.X][XUP]
    mapping[7] = mapping[19] = BPs[Basis.X][XDOWN]
    mapping[18] = BPs[Basis.X][XRIGHT]
    mapping[20] = BPs[Basis.X][XLEFT]

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
    arms: SpatialArms,
) -> QubitVerticalBorders | QubitHorizontalBorders:
    """Returns the :class:`~tqec.templates.base.Template` instance
    needed to implement the given spatial ``arms``.

    Args:
        arms: specification of the spatial arm(s) we want a template for. Needs
            to contain either one arm, or 2 arms that form a line (e.g.,
            ``SpatialArms.UP | SpatialArms.DOWN``).

    Raises:
        TQECException: if the provided ``arms`` is invalid.

    Returns:
        an instance of
        :class:`~tqec.templates.qubit.QubitHorizontalBorders` or
        :class:`~tqec.templates.qubit.QubitVerticalBorders` depending on
        the provided ``arms``.
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


def get_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
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
        arms: arm(s) of the spatial cube(s) linked by the pipe.
        reset: basis of the reset operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no reset being
            applied on data-qubits.
        measurement: basis of the measurement operation performed on **internal**
            data-qubits. Defaults to ``None`` that translates to no measurement
            being applied on data-qubits.

    Raises:
        TQECException: if ``arm`` does not contain exactly 1 or 2 flags (i.e.,
            if it contains 0 or 3+ flags).

    Returns:
        a description of the plaquettes needed to implement **one** pipe
        connecting to a spatial cube.
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
        return _get_left_right_spatial_cube_arm_rpng_descriptions(
            spatial_boundary_basis, arms, reset, measurement
        )
    if arms in [SpatialArms.UP, SpatialArms.DOWN, SpatialArms.UP | SpatialArms.DOWN]:
        return _get_up_down_spatial_cube_arm_rpng_descriptions(
            spatial_boundary_basis, arms, reset, measurement
        )
    raise TQECException(f"Got an invalid arm: {arms}.")


def _get_left_right_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # We need the bulk plaquettes to only reset the central qubits of the pipe.
    # To do so, we have two sets of bulk plaquettes with different reset/measured
    # qubits. Plaquettes that should go on the LEFT part of the pipe should
    # measure right qubits (i.e., indices 1 and 3) and conversely for the RIGHT
    # part.
    # BPs: Bulk Plaquettes
    BPs_LEFT = get_bulk_plaquettes(reset, measurement, (1, 3))
    BPs_RIGHT = get_bulk_plaquettes(reset, measurement, (0, 2))
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)
    # The hook errors also need to be adapted to the boundary basis.
    ZHOOK = (
        Orientation.HORIZONTAL
        if spatial_boundary_basis == Basis.Z
        else Orientation.VERTICAL
    )
    XHOOK = ZHOOK.flip()
    # List the plaquettes used. This mapping might be corrected afterwards to
    # avoid overwriting 3-body stabilizers introduced by the spatial cube.
    UP = 2 if spatial_boundary_basis == Basis.Z else 1
    DOWN = 3 if spatial_boundary_basis == Basis.Z else 4

    mapping = {
        # Boundaries
        # For convenience of definition here, the 2-body stabilizers never reset
        # or measure their data-qubits. If a reset/measurement is needed, it is
        # already included in the plaquettes in the bulk.
        UP: TBPs[spatial_boundary_basis][PlaquetteOrientation.UP],
        DOWN: TBPs[spatial_boundary_basis][PlaquetteOrientation.DOWN],
        # LEFT bulk
        5: BPs_LEFT[Basis.Z][ZHOOK],
        6: BPs_LEFT[Basis.X][XHOOK],
        # RIGHT bulk
        7: BPs_RIGHT[Basis.X][XHOOK],
        8: BPs_RIGHT[Basis.Z][ZHOOK],
    }
    # Remove the top plaquette if it overwrites a 3-body stabilizer.
    if (SpatialArms.LEFT in arms and spatial_boundary_basis == Basis.Z) or (
        SpatialArms.RIGHT in arms and spatial_boundary_basis == Basis.X
    ):
        del mapping[UP]
    # Remove the bottom plaquette if it overwrites a 3-body stabilizer.
    if (SpatialArms.RIGHT in arms and spatial_boundary_basis == Basis.Z) or (
        SpatialArms.LEFT in arms and spatial_boundary_basis == Basis.X
    ):
        del mapping[DOWN]
    return FrozenDefaultDict(mapping, default_factory=RPNGDescription.empty)


def _get_up_down_spatial_cube_arm_rpng_descriptions(
    spatial_boundary_basis: Basis,
    arms: SpatialArms,
    reset: Basis | None = None,
    measurement: Basis | None = None,
) -> FrozenDefaultDict[int, RPNGDescription]:
    # We need the bulk plaquettes to only reset the central qubits of the pipe.
    # To do so, we have two sets of bulk plaquettes with different reset/measured
    # qubits. Plaquettes that should go on the UP part of the pipe should measure
    # bottom qubits (i.e., indices 2 and 3) and conversely for the DOWN part.
    BPs_UP = get_bulk_plaquettes(reset, measurement, (2, 3))
    BPs_DOWN = get_bulk_plaquettes(reset, measurement, (0, 1))
    # TBPs: Two Body Plaquettes.
    TBPs = get_2_body_plaquettes(reset, measurement)
    # The hook errors also need to be adapted to the boundary basis.
    ZHOOK = (
        Orientation.VERTICAL
        if spatial_boundary_basis == Basis.Z
        else Orientation.HORIZONTAL
    )
    XHOOK = ZHOOK.flip()
    # List the plaquettes used. This mapping might be corrected afterwards to
    # avoid overwriting 3-body stabilizers introduced by the spatial cube.
    LEFT = 3 if spatial_boundary_basis == Basis.Z else 1
    RIGHT = 2 if spatial_boundary_basis == Basis.Z else 4

    mapping = {
        # Boundaries
        # For convenience of definition here, the 2-body stabilizers never reset
        # or measure their data-qubits. If a reset/measurement is needed, it is
        # already included in the plaquettes in the bulk.
        LEFT: TBPs[spatial_boundary_basis][PlaquetteOrientation.LEFT],
        RIGHT: TBPs[spatial_boundary_basis][PlaquetteOrientation.RIGHT],
        # TOP bulk
        5: BPs_UP[Basis.Z][ZHOOK],
        6: BPs_UP[Basis.X][XHOOK],
        # BOTTOM bulk
        7: BPs_DOWN[Basis.X][XHOOK],
        8: BPs_DOWN[Basis.Z][ZHOOK],
    }
    # Remove the top plaquette if it overwrites a 3-body stabilizer.
    if (SpatialArms.DOWN in arms and spatial_boundary_basis == Basis.Z) or (
        SpatialArms.UP in arms and spatial_boundary_basis == Basis.X
    ):
        del mapping[RIGHT]
    # Remove the bottom plaquette if it overwrites a 3-body stabilizer.
    if (SpatialArms.UP in arms and spatial_boundary_basis == Basis.Z) or (
        SpatialArms.DOWN in arms and spatial_boundary_basis == Basis.X
    ):
        del mapping[LEFT]
    return FrozenDefaultDict(mapping, default_factory=RPNGDescription.empty)


get_spatial_cube_qubit_plaquettes: Final = default_plaquette_mapper(
    get_spatial_cube_qubit_rpng_descriptions
)
get_spatial_cube_arm_plaquettes: Final = default_plaquette_mapper(
    get_spatial_cube_arm_rpng_descriptions
)
