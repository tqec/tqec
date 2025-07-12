from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.specs.library.generators.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.plaquette.debug import DrawPolygon, PlaquetteDebugInformation
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis
from tqec.utils.enums import Basis
from tqec.utils.instructions import (
    MEASUREMENT_INSTRUCTION_NAMES,
    RESET_INSTRUCTION_NAMES,
)
from tqec.visualisation.computation.plaquette.extended import (
    ExtendedPlaquetteDrawer,
    ExtendedPlaquettePosition,
    ExtendedPlaquetteType,
)


def _get_spatial_cube_arm_name(
    basis: Basis,
    position: Literal["UP", "DOWN"],
    reset: Basis | None,
    measurement: Basis | None,
    is_reverse: bool,
) -> str:
    parts = ["SpatialCubeArm", basis.value.upper(), position]
    if reset is not None:
        parts.append(f"R{reset.value.upper()}")
    if measurement is not None:
        parts.append(f"M{measurement.value.upper()}")
    if is_reverse:
        parts.append("reversed")
    return "_".join(parts)


def _make_spatial_cube_arm_memory_plaquette_up(
    basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reverse: bool = False,
) -> Plaquette:
    # d1 ---- d2
    # |        |
    # |   s1   |
    # |        |
    # s2 ---- s2
    qubits = PlaquetteQubits(
        [GridQubit(-1, -1), GridQubit(1, -1)],
        [GridQubit(0, 0), GridQubit(1 if is_reverse else -1, 1)],
    )
    d1, d2 = tuple(qubits.data_qubits_indices)
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
    if not is_reverse:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    b = basis.name.upper()
    schedule = EXTENDED_PLAQUETTE_SCHEDULES[is_reverse][0:2]
    for d, s in zip((d1, d2), schedule):
        base_moments[s].append(f"C{b}", [s1, d], [])
    # Add data-qubit reset/measurement if needed
    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s2] if is_reverse else [s1, s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(basis, "UP", reset, measurement, is_reverse),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


def _make_spatial_cube_arm_memory_plaquette_down(
    basis: Basis,
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reverse: bool = False,
) -> Plaquette:
    # s2 ---- s2
    # |        |
    # |   s1   |
    # |        |
    # d1 ---- d2
    qubits = PlaquetteQubits(
        [GridQubit(-1, 1), GridQubit(1, 1)],
        [GridQubit(0, 0), GridQubit(1 if is_reverse else -1, -1)],
    )
    d1, d2 = tuple(qubits.data_qubits_indices)
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
    if is_reverse:
        base_moments[0].append("RX", [s1], [])
        base_moments[1].append("CX", [s1, s2], [])
        base_moments[5].append("CX", [s2, s1], [])
    else:
        base_moments[1].append("RZ", [s1], [])
        base_moments[2].append("CX", [s2, s1], [])
        base_moments[6].append("CX", [s1, s2], [])
        base_moments[7].append("MX", [s1], [])
    # Add controlled gates
    b = basis.name.upper()
    schedule = EXTENDED_PLAQUETTE_SCHEDULES[is_reverse][2:4]
    for d, s in zip((d1, d2), schedule):
        base_moments[s].append(f"C{b}", [s1, d], [])
    # Add data-qubit reset/measurement if needed

    # Note about resets: data-qubits (i.e., the 4 corners) are already in a
    # correct state and we should not reset them. Internal qubits are also
    # already reset individually by the circuit constructed above. That means
    # that we should NOT reset anything here. Nevertheless, the reset argument
    # is kept because the plaquette naming should be adapted.
    if measurement:
        # Add ancilla measurements if data-qubits are measured.
        base_moments[-1].append("M", [s1, s2] if is_reverse else [s2], [])
    # Finally, return the plaquette
    return Plaquette(
        _get_spatial_cube_arm_name(basis, "DOWN", reset, measurement, is_reverse),
        qubits,
        ScheduledCircuit(base_moments, 0, qubits.qubit_map),
        MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES,
    )


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
        reset: basis of the reset operation performed on data-qubits. Defaults
            to ``None`` that translates to no reset being applied on data-qubits.
        measurement: basis of the measurement operation performed on data-qubits.
            Defaults to ``None`` that translates to no measurement being applied
            on data-qubits.
        is_reverse: whether the schedules of controlled-A gates are reversed.

    Returns:
        A tuple ``(UP, DOWN)`` containing the two plaquettes needed to implement
        spatial cube arms.

    """
    return (
        _make_spatial_cube_arm_memory_plaquette_up(basis, reset, measurement, is_reverse),
        _make_spatial_cube_arm_memory_plaquette_down(basis, reset, measurement, is_reverse),
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
    def _up_plaquette_polygons(basis: PauliBasis) -> list[DrawPolygon]:
        extended_corners = [
            GridQubit(-1, -1),
            GridQubit(1, -1),
            GridQubit(-1, 3),
            GridQubit(1, 3),
        ]
        return [
            DrawPolygon({basis: [extended_corners[i] for i in indices]})
            for indices in [
                # bulk
                [0, 1, 2, 3],
                # left with arm
                [1, 2, 3],
                # left without arm
                [1, 3],
                # right with arm
                [0, 1, 2],
                # right without arm
                [0, 2],
            ]
        ]

    @staticmethod
    def _get_drawers(
        basis: Basis, reset: Basis | None, measurement: Basis | None, is_reverse: bool
    ) -> tuple[
        dict[ExtendedPlaquetteType, ExtendedPlaquetteDrawer],
        dict[ExtendedPlaquetteType, ExtendedPlaquetteDrawer],
    ]:
        schedule = EXTENDED_PLAQUETTE_SCHEDULES[is_reverse]
        return (
            {
                ptype: ExtendedPlaquetteDrawer(
                    ptype, ExtendedPlaquettePosition.UP, basis, schedule, reset, measurement
                )
                for ptype in ExtendedPlaquetteType
            },
            {
                ptype: ExtendedPlaquetteDrawer(
                    ptype, ExtendedPlaquettePosition.DOWN, basis, schedule, reset, measurement
                )
                for ptype in ExtendedPlaquetteType
            },
        )

    @staticmethod
    def from_args(
        basis: Basis, reset: Basis | None, measurement: Basis | None, is_reverse: bool
    ) -> ExtendedPlaquetteCollection:
        """Build an instance of :class:`.ExtendedPlaquetteCollection` from the provided
        arguments.
        """
        up, down = make_spatial_cube_arm_plaquettes(basis, reset, measurement, is_reverse)
        up_plaquette_polygons = ExtendedPlaquetteCollection._up_plaquette_polygons(
            PauliBasis(basis.value.lower())
        )
        up_drawers, down_drawers = ExtendedPlaquetteCollection._get_drawers(
            basis, reset, measurement, is_reverse
        )
        # Work-around: debug information for the whole extended plaquette is
        # embedded in the UP plaquette, so we do not need to include anything in
        # the DOWN plaquette.
        up_plaquettes = {
            ptype: up.with_debug_information(
                PlaquetteDebugInformation(draw_polygons=polygons, drawer=up_drawers[ptype])
            )
            for polygons, ptype in zip(up_plaquette_polygons, up_drawers)
        }
        down_plaquettes = {
            ptype: down.with_debug_information(
                PlaquetteDebugInformation(drawer=down_drawers[ptype])
            )
            for ptype in down_drawers
        }
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
        _ept = ExtendedPlaquetteType
        return ExtendedPlaquetteCollection(
            bulk=ExtendedPlaquette(
                up_plaquettes[_ept.BULK],
                down_plaquettes[_ept.BULK],
            ),
            left_with_arm=ExtendedPlaquette(
                up_plaquettes[_ept.LEFT_WITH_ARM].project_on_data_qubit_indices([1]),
                down_plaquettes[_ept.LEFT_WITH_ARM],
            ),
            left_without_arm=ExtendedPlaquette(
                up_plaquettes[_ept.LEFT_WITHOUT_ARM].project_on_data_qubit_indices([1]),
                down_plaquettes[_ept.LEFT_WITHOUT_ARM].project_on_data_qubit_indices([1]),
            ),
            right_with_arm=ExtendedPlaquette(
                up_plaquettes[_ept.RIGHT_WITH_ARM],
                down_plaquettes[_ept.RIGHT_WITH_ARM].project_on_data_qubit_indices([0]),
            ),
            right_without_arm=ExtendedPlaquette(
                up_plaquettes[_ept.RIGHT_WITHOUT_ARM].project_on_data_qubit_indices([0]),
                down_plaquettes[_ept.RIGHT_WITHOUT_ARM].project_on_data_qubit_indices([0]),
            ),
        )
