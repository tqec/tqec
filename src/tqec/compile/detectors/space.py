"""Small, dependency-free helpers for linear algebra over GF(2)."""

from __future__ import annotations

from collections.abc import Iterable


class GF2Basis:
    """An incrementally constructed row-echelon basis of integer bit vectors."""

    def __init__(self, rows: Iterable[int] = ()) -> None:
        """Initialize the basis from the provided rows."""
        self._rows: dict[int, int] = {}
        self._coefficients: dict[int, int] = {}
        self._generators: list[int] = []
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
        original = row
        coefficients = 1 << self.rank
        while row:
            pivot = row.bit_length() - 1
            if pivot not in self._rows:
                break
            row ^= self._rows[pivot]
            coefficients ^= self._coefficients[pivot]
        if not row:
            return False
        pivot = row.bit_length() - 1
        self._rows[pivot] = row
        self._coefficients[pivot] = coefficients
        self._generators.append(original)
        return True

    @property
    def generators(self) -> tuple[int, ...]:
        """Return independent original rows in insertion order."""
        return tuple(self._generators)

    def decompose(self, row: int) -> int | None:
        """Express a row in ``generators`` coordinates, or return None outside the span."""
        coefficients = 0
        while row:
            pivot = row.bit_length() - 1
            if pivot not in self._rows:
                return None
            row ^= self._rows[pivot]
            coefficients ^= self._coefficients[pivot]
        return coefficients

    def contains(self, row: int) -> bool:
        """Return whether ``row`` is in the span of the basis."""
        return self.reduce(row) == 0


def gf2_row_basis(rows: Iterable[int]) -> tuple[int, ...]:
    """Return an independent basis spanning ``rows``."""
    return GF2Basis(rows).rows


def nullspace(rows: Iterable[int], width: int) -> tuple[int, ...]:
    """Return a basis of vectors orthogonal to all rows, including free columns."""
    basis = GF2Basis(rows)
    if any(row >> width for row in basis.rows):
        raise ValueError("Row exceeds the specified matrix width.")
    pivots = {row.bit_length() - 1 for row in basis.rows}
    result = []
    for column in range(width):
        if column in pivots:
            continue
        vector = 1 << column
        for row in reversed(basis.rows):
            if (row & vector).bit_count() % 2:
                vector ^= 1 << (row.bit_length() - 1)
        result.append(vector)
    return tuple(result)


def xor_rows(coefficients: int, rows: Iterable[int]) -> int:
    """Evaluate a GF(2) linear combination of rows."""
    result = 0
    for index, row in enumerate(rows):
        if coefficients >> index & 1:
            result ^= row
    return result
