"""Defines enumerations that are only used in :mod:`tqec.templates`."""

from __future__ import annotations

from enum import Enum, auto


class TemplateBorder(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()

    def opposite(self) -> TemplateBorder:
        """Return the opposite border."""
        match self:
            case TemplateBorder.TOP:
                return TemplateBorder.BOTTOM
            case TemplateBorder.BOTTOM:  # pragma: no cover
                return TemplateBorder.TOP  # pragma: no cover
            case TemplateBorder.LEFT:  # pragma: no cover
                return TemplateBorder.RIGHT  # pragma: no cover
            case TemplateBorder.RIGHT:  # pragma: no cover
                return TemplateBorder.LEFT  # pragma: no cover
