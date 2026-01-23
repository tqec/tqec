from __future__ import annotations

from collections.abc import Generator
from enum import Enum, Flag, auto

from tqec.utils.exceptions import TQECError


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

    def to_pauli(self) -> Pauli:
        """Convert to the corresponding Pauli operator."""
        match self:
            case Basis.X:
                return Pauli.X
            case Basis.Z:
                return Pauli.Z

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.value}"

    def __lt__(self, other: Basis) -> bool:
        return self.value < other.value


class PatchStyle(Enum):
    FixedBulk = auto()
    FixedBoundaryParity = auto()


# Flag is preferred over IntFlag for a number of reasons, including boundary control,
# i.e., preventing Pauli(4), etc. (enum.FlagBoundary is not available in Python 3.10)
class Pauli(Flag):
    """Pauli operators as bit flags of X and Z supports."""

    I = 0  # noqa: E741
    X = 1
    Z = 2
    Y = X | Z

    def flipped(self, condition: bool = True) -> Pauli:
        """Return the Pauli operator with X and Z supports flipped."""
        return ~self if condition else self

    def to_basis(self) -> Basis:
        """Convert to the corresponding `Basis`.

        Raises:
            TQECError: If the Pauli operator is not X or Z.

        Returns:
            The corresponding `Basis`.

        """
        match self:
            case Pauli.X:
                return Basis.X
            case Pauli.Z:
                return Basis.Z
            case _:
                raise TQECError(f"Cannot convert Pauli {self} to Basis.")

    def to_basis_set(self) -> set[Basis]:
        """Convert to the corresponding set of bases."""
        bases = list(Basis)
        return {bases[basis.value >> 1] for basis in self.iter_xz() if basis in self}

    def __invert__(self) -> Pauli:
        value = self.value
        return Pauli((value >> 1) | ((value % 2) << 1))

    def __str__(self) -> str:
        return "IXZY"[self.value]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self!s}"

    # Directly iterating over Pauli gives X, Z in Python 3.11+ but I, X, Y, Z in 3.10 due to a
    # behavior change in Flag. So we define these methods for consistent behavior across versions.
    @staticmethod
    def iter_xz() -> Generator[Pauli, None, None]:
        """Iterate over the X and Z Pauli operators."""
        yield from map(Pauli, range(1, 3))

    @staticmethod
    def iter_xzy() -> Generator[Pauli, None, None]:
        """Iterate over the X, Y, Z Pauli operators."""
        yield from map(Pauli, range(1, 4))

    @staticmethod
    def iter_ixzy() -> Generator[Pauli, None, None]:
        """Iterate over the I, X, Y, Z Pauli operators."""
        yield from map(Pauli, range(4))
