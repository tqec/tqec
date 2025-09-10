"""Defines the :class:`.Schedule` class.

The :class:`.Schedule` class is a thin wrapper around ``list[int]`` to represent a schedule.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from tqec.circuit.schedule.exception import ScheduleError


@dataclass
class Schedule:
    """Thin wrapper around ``list[int]`` to represent a schedule.

    This class ensures that the list of integers provided is a valid schedule by checking that all
    entries are positive integers, that the list is sorted and that it does not contain any
    duplicate.

    """

    schedule: list[int] = field(default_factory=list)
    """List of integers representing the schedule."""

    _INITIAL_SCHEDULE: ClassVar[int] = 0
    """First entry of a default-constructed schedule."""

    def __post_init__(self) -> None:
        Schedule._check_schedule(self.schedule)

    @staticmethod
    def from_offsets(schedule_offsets: Sequence[int]) -> Schedule:
        """Get a valid schedule from offsets.

        This method should be used to avoid any dependency on
        :py:const:`Schedule._INITIAL_SCHEDULE` in user code.

        """
        return Schedule([Schedule._INITIAL_SCHEDULE + s for s in schedule_offsets])

    @staticmethod
    def _check_schedule(schedule: list[int]) -> None:
        # Check that the schedule is sorted and positive
        if schedule and (
            not all(schedule[i] < schedule[i + 1] for i in range(len(schedule) - 1))
            or schedule[0] < Schedule._INITIAL_SCHEDULE
        ):
            raise ScheduleError(
                f"The provided schedule {schedule} is not a sorted list of positive "
                "integers. You should only provide sorted schedules with positive "
                "entries."
            )

    def __len__(self) -> int:
        return len(self.schedule)

    def __getitem__(self, i: int) -> int:
        return self.schedule[i]

    def __iter__(self) -> Iterator[int]:
        return iter(self.schedule)

    def insert(self, i: int, value: int) -> None:
        """Insert an integer to the schedule.

        If inserting the integer results in an invalid schedule, the schedule is
        brought back to its (valid) original state before calling this function
        and a :py:exc:`~.schedule.exception.ScheduleError` is raised.

        Args:
            i: index at which the provided value should be inserted.
            value: value to insert.

        Raises:
            ScheduleError: if the inserted integer makes the schedule
                invalid.

        """
        self.schedule.insert(i, value)
        try:
            Schedule._check_schedule(self.schedule)
        except ScheduleError as e:
            self.schedule.pop(i)
            raise e

    def append(self, value: int) -> None:
        """Append an integer to the schedule.

        If appending the integer results in an invalid schedule, the schedule is
        brought back to its (valid) original state before calling this function
        and a :py:exc:`~.schedule.exception.ScheduleError` is raised.

        Args:
            value: value to insert.

        Raises:
            ScheduleError: if the inserted integer makes the schedule
                invalid.

        """
        self.schedule.append(value)
        try:
            Schedule._check_schedule(self.schedule)
        except ScheduleError as e:
            self.schedule.pop(-1)
            raise e

    def append_schedule(self, schedule: Schedule) -> None:
        """Append a full schedule **after** ``self``.

        Note:
            The provided ``schedule`` is append just after ``self``. If ``self`` is empty, then we
            have ``self == schedule`` at the end of this method. If ``self`` contains at least one
            schedule, all entries of ``schedule`` are offset by the maximum schedule in ``self``
            plus 1.

        """
        starting_index = self.schedule[-1] + 1 if self.schedule else Schedule._INITIAL_SCHEDULE
        # Not using a generator here but explicitly constructing a list because
        # if `schedule == self` a generator would induce an infinite loop.
        self.schedule.extend([starting_index + s for s in schedule.schedule])

    @property
    def max_schedule(self) -> int:
        """Get the maximum timestep in ``self`` or ``0`` if ``self`` is empty."""
        return self.schedule[-1] if self.schedule else 0
