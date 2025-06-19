import random

import pytest

from tqec.circuit.schedule.exception import ScheduleException
from tqec.circuit.schedule.schedule import Schedule


def test_schedule_construction() -> None:
    Schedule([])
    Schedule([0])
    Schedule([0, 2, 4, 6])
    Schedule(list(range(100000)))

    with pytest.raises(ScheduleException):
        Schedule([-2, 0, 1])
    with pytest.raises(ScheduleException):
        Schedule([0, 1, 1, 2])
    with pytest.raises(ScheduleException):
        Schedule([1, 0])


def test_schedule_from_offset() -> None:
    Schedule.from_offsets([])
    Schedule.from_offsets([0])
    Schedule.from_offsets([0, 2, 4, 6])
    Schedule.from_offsets(list(range(100000)))

    with pytest.raises(ScheduleException):
        Schedule.from_offsets([-2, 0, 1])
    with pytest.raises(ScheduleException):
        Schedule.from_offsets([0, 1, 1, 2])
    with pytest.raises(ScheduleException):
        Schedule.from_offsets([1, 0])


def test_schedule_len() -> None:
    assert len(Schedule([])) == 0
    assert len(Schedule([0])) == 1
    assert len(Schedule([0, 2, 4, 6])) == 4
    assert len(Schedule(list(range(100000)))) == 100000


def test_schedule_getitem() -> None:
    with pytest.raises(IndexError):
        Schedule([])[0]
    with pytest.raises(IndexError):
        Schedule([])[-1]
    assert Schedule([0])[0] == 0
    assert Schedule([0, 2, 4, 6])[2] == 4
    assert Schedule([0, 2, 4, 6])[-1] == 6
    sched = Schedule(list(range(100000)))
    for i in (random.randint(0, 99999) for _ in range(100)):
        assert sched[i] == i


def test_schedule_iter() -> None:
    assert list(Schedule([])) == []
    assert list(Schedule([0, 5, 6])) == [0, 5, 6]
    assert list(Schedule(list(range(100000)))) == list(range(100000))


def test_schedule_append_schedule() -> None:
    sched = Schedule(list(range(10)))
    sched.append_schedule(sched)
    assert sched.schedule == list(range(20))


def test_schedule_insert() -> None:
    schedule = Schedule([0, 3])
    with pytest.raises(ScheduleException):
        schedule.insert(0, -1)
    assert schedule.schedule == [0, 3]
    schedule.insert(1, 1)
    assert schedule.schedule == [0, 1, 3]
    schedule.insert(-1, 2)
    assert schedule.schedule == [0, 1, 2, 3]


def test_schedule_append() -> None:
    schedule = Schedule([0, 3])
    with pytest.raises(ScheduleException):
        schedule.append(-1)
    assert schedule.schedule == [0, 3]
    schedule.append(4)
    assert schedule.schedule == [0, 3, 4]
    schedule.append(5)
    assert schedule.schedule == [0, 3, 4, 5]


def test_max_schedule() -> None:
    assert Schedule([]).max_schedule == 0
    assert Schedule([0, 1, 3, 4]).max_schedule == 4
    assert Schedule(list(range(0, 1000, 2))).max_schedule == 998
