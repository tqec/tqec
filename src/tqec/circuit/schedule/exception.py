"""Defines :class:`~tqec.circuit.schedule.exception.ScheduleError`."""

from tqec.utils.exceptions import TQECException


class ScheduleError(TQECException):
    pass


class AnnotationError(TQECException):
    pass


class UnsupportedError(TQECException):
    pass
