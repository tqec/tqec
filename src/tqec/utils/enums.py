from __future__ import annotations

from enum import Enum, auto


class Orientation(Enum):
    """Either horizontal or vertical orientation."""

    HORIZONTAL = auto()
    VERTICAL = auto()

    def flip(self) -> Orientation:
        """Flip ``self``, returning the opposite orientation."""
        return Orientation.HORIZONTAL if self == Orientation.VERTICAL else Orientation.VERTICAL


class Basis(Enum):
    X = "X"
    Z = "Z"

    def flipped(self) -> Basis:
        """Flip ``self``, returning the opposite basis."""
        return Basis.X if self == Basis.Z else Basis.Z

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.value}"

    def __lt__(self, other: Basis) -> bool:
        return self.value < other.value


class PauliBasis(Enum):
    X = "x"
    Y = "y"
    Z = "z"

    def __str__(self) -> str:
        return self.value  # pragma: no cover

    def to_extended_basis(self) -> ExtendedBasis:
        """Return ``self`` as an extended basis."""
        return ExtendedBasis(self.value)


class ExtendedBasis(Enum):
    X = PauliBasis.X.value
    Y = PauliBasis.Y.value
    Z = PauliBasis.Z.value
    H = "h"

    def __str__(self) -> str:
        return self.value  # pragma: no cover


class PatchStyle(Enum):
    FixedBulk = auto()
    FixedBoundaryParity = auto()
