"""Defines enumerations that are only used in :mod:`tqec.templates`."""

from enum import Enum, auto


class TemplateBorder(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()
