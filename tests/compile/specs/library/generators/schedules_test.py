from typing import cast

import pytest
from typing_extensions import Any

from tqec.compile.specs.library.generators.schedules import (
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

    with pytest.raises(ValueError, match="Missing interaction schedules"):
        PlaquetteScheduleFamily("incomplete", 5, schedules)


def test_schedule_family_requires_every_orientation() -> None:
    schedules = _valid_schedules()
    del schedules[Basis.X][Orientation.VERTICAL]

    with pytest.raises(ValueError, match="Missing interaction schedules"):
        PlaquetteScheduleFamily("incomplete", 5, schedules)


@pytest.mark.parametrize(
    "schedule",
    [
        PlaquetteSchedule(1, 1, 3, 4),
        PlaquetteSchedule(0, 2, 3, 4),
        PlaquetteSchedule(1, 2, 3, 5),
    ],
)
def test_schedule_family_rejects_invalid_interaction_schedules(
    schedule: PlaquetteSchedule,
) -> None:
    schedules = _valid_schedules()
    schedules[Basis.X][Orientation.HORIZONTAL] = schedule

    with pytest.raises(ValueError):
        PlaquetteScheduleFamily("invalid", 5, schedules)


def test_schedule_family_interaction_schedules_are_immutable() -> None:
    x_schedules = cast(Any, DIAGONAL_SCHEDULE_FAMILY.interaction_schedules[Basis.X])
    with pytest.raises(TypeError):
        x_schedules[Orientation.HORIZONTAL] = PlaquetteSchedule(1, 2, 3, 4)
