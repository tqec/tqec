from abc import ABC, abstractmethod

from typing_extensions import override


class ScheduleFunction(ABC):
    @abstractmethod
    def __call__(self, input_schedule: int) -> int:
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass


class ScheduleOffset(ScheduleFunction):
    def __init__(self, offset: int):
        super().__init__()
        self._offset = offset

    @override
    def __call__(self, input_schedule: int) -> int:
        return input_schedule + self._offset

    @override
    def __hash__(self) -> int:
        return 2 * self._offset


class ScheduleConstant(ScheduleFunction):
    def __init__(self, constant: int):
        super().__init__()
        self._constant = constant

    @override
    def __call__(self, input_schedule: int) -> int:
        return self._constant

    @override
    def __hash__(self) -> int:
        return 2 * self._constant + 1
