from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, cast

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.circuit.schedule.schedule import Schedule
from tqec.compile.specs.library.generators.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits
from tqec.plaquette.rpng.rpng import RPNG, PauliBasis, RPNGDescription
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import MEASUREMENT_INSTRUCTION_NAMES, RESET_INSTRUCTION_NAMES
from tqec.visualisation.computation.plaquette.extended import (
    ExtendedPlaquetteDrawer,
    ExtendedPlaquettePosition,
    ExtendedPlaquetteType,
)


def _get_spatial_cube_arm_name(
    basis_left: PauliBasis | None,
    basis_right: PauliBasis | None,
    position: Literal["UP", "DOWN", "LEFT", "RIGHT"],
    reset: Basis | None,
    measurement: Basis | None,
    is_reverse: bool,
) -> str:
    parts = ["SpatialCubeArm", position]
    if basis_left is not None:
        parts.append("L" + basis_left.name.upper())
    if basis_right is not None:
        parts.append("R" + basis_right.name.upper())
    if reset is not None:
        parts.append(f"R{reset.value.upper()}")
    if measurement is not None:
        parts.append(f"M{measurement.value.upper()}")
    if is_reverse:
        parts.append("reversed")
    return "_".join(parts)


def _check_schedules(
    schedules: Sequence[int | None], first_available_schedule: int, last_available_schedule: int
) -> None:
    considered_schedules: list[int] = [s for s in schedules if s is not None]
    for s in considered_schedules:
        if not (first_available_schedule <= s <= last_available_schedule):
            raise TQECError(
                f"Got a schedule of {s} for a part of an extended plaquette. With the current "
                f"implementation, that schedule should be between {first_available_schedule} and "
                f"{last_available_schedule} (both inclusive)."
            )
    if len(frozenset(considered_schedules)) != len(considered_schedules):
        raise TQECError(
            "Found a duplicated schedule in the provided schedules. That would lead to a qubit "
            "being used twice in the same timestep, which is not supported."
        )


def _make_spatial_cube_arm_memory_plaquette_up(
    left_qubit: RPNG,
    right_qubit: RPNG,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> Plaquette:
    # Checking the validity of the provided schedules
    first_available_schedule = 2 if not is_reversed else 3
    last_available_schedule = 4 if not is_reversed else 5
    _check_schedules(
        [left_qubit.n, right_qubit.n], first_available_schedule, last_available_schedule
    )
    # dl ---- dr
    # |        |
    # |   s1   |
    # |        |
    # s2 ---- s2
    qubits = PlaquetteQubits(
        [GridQubit(-1, -1), GridQubit(1, -1)],
        [GridQubit(0, 0), GridQubit(1 if is_reversed else -1, 1)],
    )
    dl, dr = tuple(qubits.data_qubits_indices)
    s1, s2 = tuple(qubits.syndrome_qubits_indices)
    # Define the base moments, only containing the reset on s2 as that is the
    # only operation that does not depend on the parameters of this function.
    base_moments = [
        Moment(stim.Circuit(f"RZ {s2}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
    ]
    # Add the GHZ state creation and measurement.
    if not is_reversed:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    if left_qubit.p is not None and left_qubit.n is not None:
        base_moments[left_qubit.n].append(f"C{left_qubit.p.name.upper()}", [s1, dl], [])
    if right_qubit.p is not None and right_qubit.n is not None:
        base_moments[right_qubit.n].append(f"C{right_qubit.p.name.upper()}", [s1, dr], [])
    # Add data-qubit reset/measurement if needed
    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s2] if is_reversed else [s1, s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(
            left_qubit.p, right_qubit.p, "UP", reset, measurement, is_reversed
        ),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


def _make_spatial_cube_arm_memory_plaquette_down(
    left_qubit: RPNG,
    right_qubit: RPNG,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> Plaquette:
    # Checking the validity of the provided schedules
    first_available_schedule = 3 if not is_reversed else 2
    last_available_schedule = 5 if not is_reversed else 4
    _check_schedules(
        [left_qubit.n, right_qubit.n], first_available_schedule, last_available_schedule
    )
    # s2 ---- s2
    # |        |
    # |   s1   |
    # |        |
    # dl ---- dr
    qubits = PlaquetteQubits(
        [GridQubit(-1, 1), GridQubit(1, 1)],
        [GridQubit(0, 0), GridQubit(1 if is_reversed else -1, -1)],
    )
    dl, dr = tuple(qubits.data_qubits_indices)
    s1, s2 = tuple(qubits.syndrome_qubits_indices)
    # Define the base moments, only containing the reset on s2 as that is the
    # only operation that does not depend on the parameters of this function.
    base_moments = [
        Moment(stim.Circuit(f"RZ {s2}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
    ]
    # Add the GHZ state creation and measurement.
    if is_reversed:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    if left_qubit.p is not None and left_qubit.n is not None:
        base_moments[left_qubit.n].append(f"C{left_qubit.p.name.upper()}", [s1, dl], [])
    if right_qubit.p is not None and right_qubit.n is not None:
        base_moments[right_qubit.n].append(f"C{right_qubit.p.name.upper()}", [s1, dr], [])
    # Add data-qubit reset/measurement if needed
    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s1, s2] if is_reversed else [s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(
            left_qubit.p, right_qubit.p, "DOWN", reset, measurement, is_reversed
        ),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


def _make_spatial_cube_arm_memory_plaquette_left(
    top_qubit: RPNG,
    bottom_qubit: RPNG,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> Plaquette:
    # Checking the validity of the provided schedules
    first_available_schedule = 2 if not is_reversed else 3
    last_available_schedule = 4 if not is_reversed else 5
    _check_schedules(
        [top_qubit.n, bottom_qubit.n], first_available_schedule, last_available_schedule
    )
    # dl ---- s2
    # |        |
    # |   s1   |
    # |        |
    # dr ---- s2
    qubits = PlaquetteQubits(
        [GridQubit(-1, -1), GridQubit(-1, 1)],
        [GridQubit(0, 0), GridQubit(1, -1 if not is_reversed else 1)],
    )
    dl, dr = tuple(qubits.data_qubits_indices)
    s1, s2 = tuple(qubits.syndrome_qubits_indices)
    # Define the base moments, only containing the reset on s2 as that is the
    # only operation that does not depend on the parameters of this function.
    base_moments = [
        Moment(stim.Circuit(f"RZ {s2}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
    ]
    # Add the GHZ state creation and measurement.
    if not is_reversed:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    if top_qubit.p is not None and top_qubit.n is not None:
        base_moments[top_qubit.n].append(f"C{top_qubit.p.name.upper()}", [s1, dl], [])
    if bottom_qubit.p is not None and bottom_qubit.n is not None:
        base_moments[bottom_qubit.n].append(f"C{bottom_qubit.p.name.upper()}", [s1, dr], [])
    # Add data-qubit reset/measurement if needed
    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s2] if is_reversed else [s1, s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(
            top_qubit.p, bottom_qubit.p, "LEFT", reset, measurement, is_reversed
        ),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


def _make_spatial_cube_arm_memory_plaquette_right(
    top_qubit: RPNG,
    bottom_qubit: RPNG,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> Plaquette:
    # Checking the validity of the provided schedules
    first_available_schedule = 3 if not is_reversed else 2
    last_available_schedule = 5 if not is_reversed else 4
    _check_schedules(
        [top_qubit.n, bottom_qubit.n], first_available_schedule, last_available_schedule
    )
    # s2 ---- dl
    # |        |
    # |   s1   |
    # |        |
    # s2 ---- dr
    qubits = PlaquetteQubits(
        [GridQubit(1, -1), GridQubit(1, 1)],
        [GridQubit(0, 0), GridQubit(-1, -1 if not is_reversed else 1)],
    )
    dl, dr = tuple(qubits.data_qubits_indices)
    s1, s2 = tuple(qubits.syndrome_qubits_indices)
    # Define the base moments, only containing the reset on s2 as that is the
    # only operation that does not depend on the parameters of this function.
    base_moments = [
        Moment(stim.Circuit(f"RZ {s2}")),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
        Moment(stim.Circuit()),
    ]
    # Add the GHZ state creation and measurement.
    if is_reversed:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    if top_qubit.p is not None and top_qubit.n is not None:
        base_moments[top_qubit.n].append(f"C{top_qubit.p.name.upper()}", [s1, dl], [])
    if bottom_qubit.p is not None and bottom_qubit.n is not None:
        base_moments[bottom_qubit.n].append(f"C{bottom_qubit.p.name.upper()}", [s1, dr], [])
    # Add data-qubit reset/measurement if needed
    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s1, s2] if is_reversed else [s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(
            top_qubit.p, bottom_qubit.p, "RIGHT", reset, measurement, is_reversed
        ),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


def get_extended_plaquette(
    rpng: RPNGDescription,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> tuple[Plaquette, Plaquette]:
    """Create an extended plaquette from the provided RPNG description.

    Args:
        rpng: description of the 4 corners of the extended plaquette.
        reset: basis of the reset operation performed on internal data-qubits (used as syndrome
            qubits). Defaults to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on internal data-qubits (used as
            syndrome qubits). Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.
        is_reversed: flag indicating if the plaquette schedule should be reversed or not. Useful to
            limit the loss of code distance when hook errors are not correctly oriented by
            alternating regular and reversed plaquettes.

    Returns:
        a pair of plaquettes ``(UP, DOWN)`` implementing the extended stabilizer.

    """
    tl, tr, bl, br = rpng.corners
    return (
        _make_spatial_cube_arm_memory_plaquette_up(tl, tr, reset, measurement, is_reversed),
        _make_spatial_cube_arm_memory_plaquette_down(bl, br, reset, measurement, is_reversed),
    )


def get_horizontal_extended_plaquette(
    rpng: RPNGDescription,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reversed: bool = False,
) -> tuple[Plaquette, Plaquette]:
    """Create a horizontal extended plaquette from the provided RPNG description.

    Args:
        rpng: description of the 4 corners of the extended plaquette.
        reset: basis of the reset operation performed on internal data-qubits (used as syndrome
            qubits). Defaults to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on internal data-qubits (used as
            syndrome qubits). Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.
        is_reversed: flag indicating if the plaquette schedule should be reversed or not. Useful to
            limit the loss of code distance when hook errors are not correctly oriented by
            alternating regular and reversed plaquettes.

    Returns:
        a pair of plaquettes ``(LEFT, RIGHT)`` implementing the extended stabilizer.

    """
    tl, tr, bl, br = rpng.corners
    return (
        _make_spatial_cube_arm_memory_plaquette_left(
            tl, bl, reset, measurement, is_reversed
        ),
        _make_spatial_cube_arm_memory_plaquette_right(
            tr, br, reset, measurement, is_reversed
        ),
    )


@dataclass(frozen=True)
class ExtendedPlaquette:
    top: Plaquette
    bottom: Plaquette


def _get_drawer_basis(description: RPNGDescription) -> PauliBasis | None:
    bases = {corner.p for corner in description.corners if corner.p is not None}
    if len(bases) == 1:
        return bases.pop()
    return None


def _get_drawer_schedule(description: RPNGDescription) -> tuple[int, int, int, int]:
    return cast(tuple[int, int, int, int], tuple(corner.n or 0 for corner in description.corners))


def _raise_if_undefined_corners(description: RPNGDescription) -> None:
    """Require a fully specified source description before deriving border shapes."""
    undefined_corners = [
        index
        for index, corner in enumerate(description.corners)
        if corner.p is None or corner.n is None
    ]
    if undefined_corners:
        raise TQECError(
            "Extended plaquette descriptions must define all four data-qubit interactions. "
            f"Undefined corner indices: {undefined_corners}."
        )


def _with_extended_plaquette_drawer(
    plaquette: Plaquette,
    plaquette_type: ExtendedPlaquetteType,
    position: ExtendedPlaquettePosition,
    basis: PauliBasis | None,
    schedule: tuple[int, int, int, int],
    reset: Basis | None,
    measurement: Basis | None,
) -> Plaquette:
    drawer = ExtendedPlaquetteDrawer(plaquette_type, position, basis, schedule, reset, measurement)
    return plaquette.with_debug_information(replace(plaquette.debug_information, drawer=drawer))


def _make_extended_plaquette(
    top: Plaquette,
    bottom: Plaquette,
    plaquette_type: ExtendedPlaquetteType,
    basis: PauliBasis | None,
    schedule: tuple[int, int, int, int],
    reset: Basis | None,
    measurement: Basis | None,
    first_position: ExtendedPlaquettePosition = ExtendedPlaquettePosition.UP,
) -> ExtendedPlaquette:
    return ExtendedPlaquette(
        _with_extended_plaquette_drawer(
            top,
            plaquette_type,
            first_position,
            basis,
            schedule,
            reset,
            measurement,
        ),
        _with_extended_plaquette_drawer(
            bottom,
            plaquette_type,
            first_position.flip(),
            basis,
            schedule,
            reset,
            measurement,
        ),
    )


@dataclass(frozen=True)
class ExtendedPlaquetteCollection:
    """The names reflect the shape of the extended plaquette. E.g.
    left_half_rectangle is the left half of the full rectangle.
    bottom_right_triangle: the right angle of the triangle is
    in the bottom right corner.

    In ``LEFT_RIGHT`` orientation the names keep the vertical shapes:
    the geometry is the transposition ``T(x, y) = (y/2, 2x)`` of the
    ``UP_DOWN`` one, so e.g. ``left_half_rectangle`` selects the top row
    (the transposed left half) and ``right_half_rectangle`` the bottom row.
    """

    bulk: ExtendedPlaquette
    bottom_right_triangle: ExtendedPlaquette
    right_half_rectangle: ExtendedPlaquette
    top_left_triangle: ExtendedPlaquette
    left_half_rectangle: ExtendedPlaquette
    bottom_left_triangle: ExtendedPlaquette
    top_right_triangle: ExtendedPlaquette

    @staticmethod
    def from_description(
        description: RPNGDescription,
        reset: Basis | None,
        measurement: Basis | None,
        is_reversed: bool,
        orientation: Literal["UP_DOWN", "LEFT_RIGHT"] = "UP_DOWN",
    ) -> ExtendedPlaquetteCollection:
        """Build an instance from the provided ``RPNGDescription``.

        Args:
            description: description of the 4 corners of the extended plaquette.
            reset: basis of the reset operation performed on internal data-qubits (used as syndrome
                qubits). Defaults to ``None`` that translates to no reset being applied on
                data-qubits.
            measurement: basis of the measurement operation performed on internal data-qubits
                (used as syndrome qubits). Defaults to ``None`` that translates to no measurement
                being applied on data-qubits.
            is_reversed: flag indicating if the plaquette schedule should be reversed or not.
            orientation: orientation of the extended stabilisers. ``"UP_DOWN"`` (the default)
                builds vertical extended stabilisers with a long direction along the y axis,
                ``"LEFT_RIGHT"`` builds horizontal extended stabilisers with a long direction
                along the x axis.

        Returns:
            a collection of extended plaquettes in the requested orientation.

        """
        _raise_if_undefined_corners(description)
        if orientation == "LEFT_RIGHT":
            first, second = get_horizontal_extended_plaquette(
                description, reset, measurement, is_reversed
            )
            first_position = ExtendedPlaquettePosition.LEFT
        else:
            first, second = get_extended_plaquette(
                description, reset, measurement, is_reversed
            )
            first_position = ExtendedPlaquettePosition.UP
        drawer_basis = _get_drawer_basis(description)
        drawer_schedule = _get_drawer_schedule(description)
        # In the calls to project_on_data_qubit_indices, it is important to remember
        # that individual plaquettes composing the extended plaquette have slightly
        # unconventional qubit layouts. In the below ASCII representation, "s" means
        # "syndrome qubit", "d" means "data qubit", the numbers are the respective
        # qubit indices. "s3" appears at two places because it swaps between the
        # two locations depending on whether the plaquette is reversed or not.
        # UP:
        # d0 ---- d1
        # |        |
        # |   s2   |
        # |        |
        # s3 ---- s3
        # DOWN:
        # s3 ---- s3
        # |        |
        # |   s2   |
        # |        |
        # d0 ---- d1
        return ExtendedPlaquetteCollection(
            bulk=_make_extended_plaquette(
                first,
                second,
                ExtendedPlaquetteType.BULK,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            bottom_right_triangle=_make_extended_plaquette(
                first.project_on_data_qubit_indices([1]),
                second,
                ExtendedPlaquetteType.BOTTOM_RIGHT_TRIANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            right_half_rectangle=_make_extended_plaquette(
                first.project_on_data_qubit_indices([1]),
                second.project_on_data_qubit_indices([1]),
                ExtendedPlaquetteType.RIGHT_HALF_RECTANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            top_left_triangle=_make_extended_plaquette(
                first,
                second.project_on_data_qubit_indices([0]),
                ExtendedPlaquetteType.TOP_LEFT_TRIANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            left_half_rectangle=_make_extended_plaquette(
                first.project_on_data_qubit_indices([0]),
                second.project_on_data_qubit_indices([0]),
                ExtendedPlaquetteType.LEFT_HALF_RECTANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            bottom_left_triangle=_make_extended_plaquette(
                first.project_on_data_qubit_indices([0]),
                second,
                ExtendedPlaquetteType.BOTTOM_LEFT_TRIANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
            # top right refers to where the right angle is.
            top_right_triangle=_make_extended_plaquette(
                first,
                second.project_on_data_qubit_indices([1]),
                ExtendedPlaquetteType.TOP_RIGHT_TRIANGLE,
                drawer_basis,
                drawer_schedule,
                reset,
                measurement,
                first_position,
            ),
        )

    @staticmethod
    def from_basis(
        basis: Basis,
        reset: Basis | None,
        measurement: Basis | None,
        is_reversed: bool,
        schedule: Sequence[int] | Schedule | None = None,
        orientation: Literal["UP_DOWN", "LEFT_RIGHT"] = "UP_DOWN",
    ) -> ExtendedPlaquetteCollection:
        """Create an instance from a basis and a schedule.

        This allows one to create an extended plaquette that measures its four corners in the
        provided basis, with the provided schedule. It does not allow mixed-basis plaquette, and as
        such it is a strictly less capable version of :meth:`from_description`, but it might be more
        convenient to use.

        Args:
            basis: stabilizer that will be measured on all the corners of the returned extended
                stabilizers.
            reset: basis of the reset operation performed on internal data-qubits (used as syndrome
                qubits). Defaults to ``None`` that translates to no reset being applied on
                data-qubits.
            measurement: basis of the measurement operation performed on internal data-qubits (used
                as syndrome qubits). Defaults to ``None`` that translates to no measurement being
                applied on data-qubits.
            is_reversed: flag indicating if the plaquette schedule should be reversed or not. Useful
                to limit the loss of code distance when hook errors are not correctly oriented by
                alternating regular and reversed plaquettes.
            schedule: if provided, the returned extended plaquettes will unconditionally implement
                this schedule (no matter the provided value of ``is_reversed``, it is up to the
                caller to ensure the provided value is valid). If not provided, a default schedule
                that depends on ``is_reversed`` is used. Needs to contain exactly 4 integer entries.
            orientation: orientation of the pair of returned extended plaquettes. ``"UP_DOWN"``
                returns the standard vertical extended plaquettes, while ``"LEFT_RIGHT"`` returns
                the horizontal ones, with data-qubits on the left/right columns.

        Returns:
            a collection of extended plaquettes measuring the provided basis on data-qubits in the
            given schedule.

        """
        if schedule is None:
            schedule = EXTENDED_PLAQUETTE_SCHEDULES[is_reversed]
        # Not including reset and measurement in the RPNG description as these are specially placed
        # for an extended plaquette
        description = RPNGDescription.from_basis_and_schedule(basis, schedule)
        return ExtendedPlaquetteCollection.from_description(
            description, reset, measurement, is_reversed, orientation
        )
