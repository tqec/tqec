"""Small, dependency-free helpers for linear algebra over GF(2)."""

from __future__ import annotations

from collections.abc import Iterable


class GF2Basis:
    """An incrementally constructed row-echelon basis of integer bit vectors."""

    def __init__(self, rows: Iterable[int] = ()) -> None:
        """Initialize the basis from the provided rows."""
        self._rows: dict[int, int] = {}
        for row in rows:
            self.add(row)

    @property
    def rank(self) -> int:
        """Return the number of independent rows in the basis."""
        return len(self._rows)

    @property
    def rows(self) -> tuple[int, ...]:
        """Return the echelon rows, ordered by decreasing pivot."""
        return tuple(self._rows[pivot] for pivot in sorted(self._rows, reverse=True))

    def reduce(self, row: int) -> int:
        """Reduce ``row`` using the basis and return its remainder."""
        while row:
            pivot = row.bit_length() - 1
            basis_row = self._rows.get(pivot)
            if basis_row is None:
                break
            row ^= basis_row
        return row

    def add(self, row: int) -> bool:
        """Add ``row`` if independent, returning whether the rank increased."""
        row = self.reduce(row)
        if not row:
            return False
        pivot = row.bit_length() - 1
        self._rows[pivot] = row
        return True

    def contains(self, row: int) -> bool:
        """Return whether ``row`` is in the span of the basis."""
        return self.reduce(row) == 0


def gf2_row_basis(rows: Iterable[int]) -> tuple[int, ...]:
    """Return an independent basis spanning ``rows``."""
    return GF2Basis(rows).rows
