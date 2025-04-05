"""Defines enumerations that are only used in :mod:`tqec.templates`."""

from __future__ import annotations

from enum import Enum, auto


class TemplateBorder(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()

    def opposite(self) -> TemplateBorder:
        match self:
            case TemplateBorder.TOP:
                return TemplateBorder.BOTTOM
            case TemplateBorder.BOTTOM:
                return TemplateBorder.TOP
            case TemplateBorder.LEFT:
                return TemplateBorder.RIGHT
            case TemplateBorder.RIGHT:
                return TemplateBorder.LEFT
