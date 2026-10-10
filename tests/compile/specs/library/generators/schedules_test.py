from typing import cast

import pytest
from typing_extensions import Any

from tqec.compile.specs.library.generators.schedules import (
    DEFAULT_SCHEDULE_FAMILY,
    DIAGONAL_SCHEDULE_FAMILY,
    PlaquetteSchedule,
    PlaquetteScheduleFamily,
)
from tqec.utils.enums import Basis, Orientation


def _valid_schedules() -> dict[Basis, dict[Orientation, PlaquetteSchedule]]:
    return {
        basis: {
            Orientation.HORIZONTAL: PlaquetteSchedule(1, 2, 3, 4),
            Orientation.VERTICAL: PlaquetteSchedule(1, 2, 3, 4),
        }
        for basis in Basis
    }


def test_schedule_family_requires_every_basis() -> None:
    schedules = _valid_schedules()
    del schedules[Basis.Z]

    with pytest.raises(ValueError, match="Missing gate schedules"):
        PlaquetteScheduleFamily("incomplete", 5, schedules)


def test_schedule_family_requires_every_orientation() -> None:
    schedules = _valid_schedules()
    del schedules[Basis.X][Orientation.VERTICAL]

    with pytest.raises(ValueError, match="Missing gate schedules"):
        PlaquetteScheduleFamily("incomplete", 5, schedules)


@pytest.mark.parametrize(
    "schedule",
    [
        PlaquetteSchedule(1, 1, 3, 4),
        PlaquetteSchedule(0, 2, 3, 4),
        PlaquetteSchedule(1, 2, 3, 5),
    ],
)
def test_schedule_family_rejects_invalid_gate_schedules(
    schedule: PlaquetteSchedule,
) -> None:
    schedules = _valid_schedules()
    schedules[Basis.X][Orientation.HORIZONTAL] = schedule

    with pytest.raises(ValueError):
        PlaquetteScheduleFamily("invalid", 5, schedules)


def test_schedule_family_gate_schedules_are_immutable() -> None:
    x_schedules = cast(Any, DIAGONAL_SCHEDULE_FAMILY.gate_schedules[Basis.X])
    with pytest.raises(TypeError):
        x_schedules[Orientation.HORIZONTAL] = PlaquetteSchedule(1, 2, 3, 4)


# ---------------------------------------------------------------------------
# Tests for PlaquetteSchedule.reversed()
# ---------------------------------------------------------------------------

#: (original top_left, top_right, bottom_left, bottom_right) -> reversed tuple
_REVERSED_CASES: list[tuple[PlaquetteSchedule, tuple[int, int, int, int]]] = [
    # Default family: vertical hook (1,4,3,5) -> (5,3,4,1)
    (
        DEFAULT_SCHEDULE_FAMILY.gate_schedules[Basis.X][Orientation.VERTICAL],
        (5, 3, 4, 1),
    ),
    # Default family: horizontal hook (1,2,3,5) -> (5,3,2,1)
    (
        DEFAULT_SCHEDULE_FAMILY.gate_schedules[Basis.X][Orientation.HORIZONTAL],
        (5, 3, 2, 1),
    ),
    # Diagonal family X: (7,5,4,6) -> (6,4,5,7)
    (
        DIAGONAL_SCHEDULE_FAMILY.gate_schedules[Basis.X][Orientation.VERTICAL],
        (6, 4, 5, 7),
    ),
    # Diagonal family Z: (1,3,4,2) -> (2,4,3,1)
    (
        DIAGONAL_SCHEDULE_FAMILY.gate_schedules[Basis.Z][Orientation.VERTICAL],
        (2, 4, 3, 1),
    ),
]


@pytest.mark.parametrize(("original", "expected_values"), _REVERSED_CASES)
def test_plaquette_schedule_reversed(
    original: PlaquetteSchedule,
    expected_values: tuple[int, int, int, int],
) -> None:
    """reversed() maps (tl,tr,bl,br) -> (br,bl,tr,tl)."""
    rev = original.reversed()
    assert rev.values == expected_values


@pytest.mark.parametrize(("original", "_"), _REVERSED_CASES)
def test_plaquette_schedule_reversed_roundtrip(
    original: PlaquetteSchedule,
    _: object,
) -> None:
    """reversed().reversed() must equal the original."""
    assert original.reversed().reversed() == original
