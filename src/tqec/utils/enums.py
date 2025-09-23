from __future__ import annotations

from enum import Enum, auto
from typing import Literal


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


class Pauli(Enum):
    I = "I"  # noqa: E741
    X = "X"
    Y = "Y"
    Z = "Z"

    def flipped(self) -> Pauli:
        """Flip ``self``, returning the opposite Pauli."""
        if self == Pauli.X:
            return Pauli.Z
        if self == Pauli.Z:
            return Pauli.X
        return self

    def has_x(self) -> bool:
        """Return True if ``self`` has an X component."""
        return self in (Pauli.X, Pauli.Y)

    def has_z(self) -> bool:
        """Return True if ``self`` has a Z component."""
        return self in (Pauli.Z, Pauli.Y)

    def has_basis(self, basis: Basis | Literal["X", "Z"]) -> bool:
        """Return True if ``self`` has the given basis component."""
        if isinstance(basis, str):
            basis = Basis(basis)
        if basis == Basis.X:
            return self.has_x()
        return self.has_z()

    def __mul__(self, other: Pauli) -> Pauli:
        if self == Pauli.I:
            return other
        if other == Pauli.I:
            return self
        if self == other:
            return Pauli.I
        if {self, other} == {Pauli.X, Pauli.Z}:
            return Pauli.Y
        if {self, other} == {Pauli.X, Pauli.Y}:
            return Pauli.Z
        return Pauli.X


class PatchStyle(Enum):
    FixedBulk = auto()
    FixedBoundaryParity = auto()
