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

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Basis.{self.value}"

    def __lt__(self, other: Basis) -> bool:
        return self.value < other.value
