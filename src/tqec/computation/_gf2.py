"""GF(2) linear algebra over bit-packed vectors, shared by the correlation-surface code.

The correlation-surface search and the conditional-surface compiler both represent a GF(2)
vector as a single Python integer, one bit per coordinate, so that XOR of vectors and masking
of coordinate subsets run at native big-integer speed at arbitrary width. This module holds the
provenance-tracking Gaussian elimination primitives they share.

The central data structure is an *echelon basis*: a ``dict`` mapping the leading set bit of each
independent vector to a ``(vector, mask)`` pair, where ``mask`` is a second bit-packed integer
recording which original rows XOR to ``vector``. Reducing a new row against the basis carries the
mask along, so a row that reduces to zero yields the combination of original rows reproducing it
-- a kernel element, a solution, or a linear-dependence witness, depending on the caller.
"""

from __future__ import annotations

from collections.abc import Sequence


def _reduce_row(
    echelon: dict[int, tuple[int, int]], vector: int, mask: int, insert: bool
) -> tuple[int, int] | None:
    """Reduce ``(vector, mask)`` against the echelon rows, XORing the masks along.

    This is the core primitive of the module. If the vector reduces to zero, return the reduced
    ``(0, mask)`` pair: ``mask`` is then a combination reproducing the original vector from the
    echelon rows (a kernel element when the original row came from a generator, a solution when
    it was a target). Otherwise the row is independent: return ``None`` after inserting it into
    ``echelon`` if ``insert`` is set.
    """
    while vector:
        lead = vector.bit_length() - 1
        if lead not in echelon:
            if insert:
                echelon[lead] = (vector, mask)
            return None
        pivot_vector, pivot_mask = echelon[lead]
        vector ^= pivot_vector
        mask ^= pivot_mask
    return (0, mask)


def _combination_indices(
    basis: dict[int, tuple[int, int]], x: int, update_basis: bool = True
) -> tuple[int, ...] | None:
    """Express ``x`` as a XOR combination of the echelon ``basis`` rows.

    The provenance masks are assigned automatically: the row inserted when ``basis`` holds ``n``
    rows is tagged with bit ``n``, so the mask returned by :func:`_reduce_row` indexes the rows
    by insertion order.

    Returns:
        The insertion indices of the basis rows XORing to ``x``, or ``None`` when ``x`` is
        independent of the basis, in which case ``x`` is appended to ``basis`` if ``update_basis``
        is set. The empty tuple means ``x`` is zero, i.e. the empty combination.

    """
    reduced = _reduce_row(basis, x, 1 << len(basis), insert=update_basis)
    if reduced is None:
        return None
    # The mask's highest bit is the self-tag ``1 << len(basis)`` of the reduced-away row; drop it
    # to leave the indices of the basis rows that combine to ``x``.
    return _int_to_bit_indices(reduced[1])[:-1]


def _solve_parity_constraints(rows: Sequence[tuple[int, int]], width: int) -> int | None:
    """Solve a set of GF(2) parity constraints for one satisfying vector.

    Each row is a ``(coefficients, target)`` pair over ``width`` coordinates; the vector ``c``
    satisfies it when ``parity(coefficients & c) == target``. Runs one Gaussian elimination over
    all the rows.

    Returns:
        A particular solution (free coordinates set to zero) satisfying every row, or ``None``
        if the rows are jointly inconsistent, i.e. no single vector satisfies all of them.

    """
    # Gaussian elimination on the augmented rows (target bit above the coefficients).
    pivots: dict[int, int] = {}
    for coefficients, target in rows:
        row = coefficients | (target << width)
        while row & ((1 << width) - 1):
            lead = (row & ((1 << width) - 1)).bit_length() - 1
            if lead not in pivots:
                pivots[lead] = row
                break
            row ^= pivots[lead]
        else:
            if row:  # 0 == 1: inconsistent system
                return None
    # Back-substitute with the free coordinates set to zero, sweeping ascending leads.
    solution = 0
    for lead in sorted(pivots):
        row = pivots[lead]
        value = ((row >> width) & 1) ^ ((row & solution).bit_count() & 1)
        solution |= value << lead
    return solution


def _int_to_bit_indices(x: int) -> tuple[int, ...]:
    """Convert an integer to a list of indices where the bits are set."""
    return tuple(i for i in range(x.bit_length()) if (x >> i) & 1)


def _normalize_basis(
    basis: dict[int, tuple[int, int]], in_place: bool = True
) -> dict[int, tuple[int, int]]:
    """Normalize the basis vectors to only have leading 1s when possible."""
    normalized_basis = basis if in_place else {}
    highest_bits = sorted(basis, reverse=True)
    for i, key in enumerate(highest_bits):
        vector, mask = basis[key]
        for highest_bit in highest_bits[i + 1 :]:
            if (vector >> highest_bit) & 1:
                pivot, pivot_mask = basis[highest_bit]
                vector ^= pivot
                mask ^= pivot_mask
        normalized_basis[key] = (vector, mask)
    return normalized_basis
