from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import override

from tqec.utils.exceptions import TQECError


class ScheduleFunction(ABC):
    """Interface for classes that can map schedules to other schedules."""

    @abstractmethod
    def __call__(self, input_schedule: int) -> int:
        """Transform the provided ``input_schedule`` to a new schedule and return it."""
        pass


@dataclass(frozen=True)
class ScheduleOffset(ScheduleFunction):
    """Maps a schedule by applying a relative offset to it."""

    offset: int

    @override
    def __call__(self, input_schedule: int) -> int:
        return input_schedule + self.offset


@dataclass(frozen=True)
class ScheduleConstant(ScheduleFunction):
    """Maps a schedule to a constant."""

    constant: int

    def __post_init__(self) -> None:
        if self.constant < 0:
            raise TQECError(
                "Cannot have a negative schedule. "
                f"The provided constant is negative: {self.constant}."
            )

    @override
    def __call__(self, input_schedule: int) -> int:
        return self.constant
