from __future__ import annotations

from enum import Enum, auto


class Orientation(Enum):
    """Either horizontal or vertical orientation."""

    HORIZONTAL = auto()
    VERTICAL = auto()


class Basis(Enum):
    X = "X"
    Z = "Z"

    def flipped(self) -> Basis:
        return Basis.X if self == Basis.Z else Basis.Z
