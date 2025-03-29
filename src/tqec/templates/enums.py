"""Defines enumerations that are only used in :mod:`tqec.templates`."""

from __future__ import annotations

from enum import Enum, auto
from typing import Literal


class ZObservableOrientation(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()

    def horizontal_basis(self) -> Literal["x", "z"]:
        return "z" if self == ZObservableOrientation.HORIZONTAL else "x"

    def vertical_basis(self) -> Literal["x", "z"]:
        return "z" if self == ZObservableOrientation.VERTICAL else "x"


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
