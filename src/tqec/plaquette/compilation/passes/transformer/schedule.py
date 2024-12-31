from abc import ABC, abstractmethod

from typing_extensions import override


class ScheduleFunction(ABC):
    """Interface for classes that can map schedules to other schedules."""

    @abstractmethod
    def __call__(self, input_schedule: int) -> int:
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass


class ScheduleOffset(ScheduleFunction):
    """Maps a schedule by applying a relative offset to it."""

    def __init__(self, offset: int):
        super().__init__()
        self._offset = offset

    @override
    def __call__(self, input_schedule: int) -> int:
        return input_schedule + self._offset

    @override
    def __hash__(self) -> int:
        # Implementation note: only valid because there are only 2 classes
        # implementing the ScheduleFunction.__hash__ method. Even hash numbers
        # are used by ScheduleOffset and odd ones by ScheduleConstant.
        return 2 * self._offset


class ScheduleConstant(ScheduleFunction):
    """Maps a schedule to a constant."""

    def __init__(self, constant: int):
        super().__init__()
        self._constant = constant

    @override
    def __call__(self, input_schedule: int) -> int:
        return self._constant

    @override
    def __hash__(self) -> int:
        # Implementation note: only valid because there are only 2 classes
        # implementing the ScheduleFunction.__hash__ method. Even hash numbers
        # are used by ScheduleOffset and odd ones by ScheduleConstant.
        return 2 * self._constant + 1
