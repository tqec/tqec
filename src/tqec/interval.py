"""Defines the :class:`Interval` data-structure to represent intervals on
:math:`\\mathbb{R}`."""

from __future__ import annotations

import math
import typing
from dataclasses import dataclass

from tqec.exceptions import TQECException


@dataclass(frozen=True)
class Interval:
    """A subset of the mathematical space representing real numbers:
    :math:`\\mathbb{R}`.

    This class represents the mathematical object called interval. It stores
    two floating-point numbers representing the bounds of the interval as
    well as two booleans (one for each bound) to know if the corresponding
    bound is included in the interval or excluded from it.

    Raises:
        TQECException: if any bound is NaN.
        TQECException: if the provided ``start`` value is strictly larger than
            the provided ``end`` value.

    Attributes:
        start: beginning of the interval. Included in the interval iff
            ``not self.start_excluded``, else it is excluded from the interval.
        end: end of the interval. Included in the interval iff
            ``not self.end_excluded``, else it is excluded from the interval.
        start_excluded: controls if ``self.start`` is included in the represented
            interval or not. Default to ``False`` which means that ``self.start``
            is included.
        end_excluded: controls if ``self.end`` is included in the represented
            interval or not. Default to ``True`` which means that ``self.end``
            is excluded.
    """

    start: float | int
    end: float | int
    start_excluded: bool = False
    end_excluded: bool = True

    def __post_init__(self) -> None:
        if math.isnan(self.start) or math.isnan(self.end):
            raise TQECException("Cannot create an Interval with a NaN bound.")
        if not self.start <= self.end:
            raise TQECException(
                f"Cannot create an interval with start={self.start} > end={self.end}."
            )

    def _is_over_start(self, value: float) -> bool:
        """Compare the provided value to ``self.start``, taking into account
        ``self.start_excluded``.

        This method checks if the provided value is contained in the interval that
        has the same ``start`` boundary as self but with +inf as ``end`` boundary.

        Args:
            value: the value to compare to start.

        Returns:
            ``True`` if ``Interval(self.start, float("inf"), self.start_excluded,
            True).contains(value)``.
        """
        return self.start < value if self.start_excluded else self.start <= value

    def _is_below_end(self, value: float) -> bool:
        """Compare the provided value to ``self.end``, taking into account
        ``self.end_excluded``.

        This method checks if the provided value is contained in the interval that
        has the same ``end`` boundary as self but with -inf as ``start`` boundary.

        Args:
            value: the value to compare to end.

        Returns:
            ``True`` if ``Interval(float("-inf"), self.end, True,
            self.end_excluded).contains(value)``.
        """
        return value < self.end if self.end_excluded else value <= self.end

    def contains(self, value: float) -> bool:
        """Returns ``True`` if ``self`` contains the provided ``value``, else
        ``False``."""
        return self._is_over_start(value) and self._is_below_end(value)

    def overlaps_with(self, other: Interval) -> bool:
        """Returns ``True`` if ``self`` overlaps with the provided interval,
        else ``False``."""
        return not self.is_disjoint(other)

    def is_disjoint(self, other: Interval) -> bool:
        """Returns ``True`` if ``self`` does not overlap with the provided
        interval, else ``False``."""
        other_end_lt_self_start = other.end < self.start or (
            other.end == self.start and (other.end_excluded or self.start_excluded)
        )
        self_end_lt_other_start = self.end < other.start or (
            self.end == other.start and (self.end_excluded or other.start_excluded)
        )
        return other_end_lt_self_start or self_end_lt_other_start

    def is_empty(self) -> bool:
        """Returns ``True`` if ``self`` is the empty interval, else
        ``False``."""
        return self.start == self.end and (self.start_excluded or self.end_excluded)

    def intersection(self, other: Interval) -> Interval:
        """Compute and return the intersection of ``self`` and ``other``."""
        if self.is_disjoint(other):
            return EMPTY_INTERVAL

        start, start_excluded = max(
            (self.start, self.start_excluded), (other.start, other.start_excluded)
        )
        if self.start == other.start:
            start_excluded = self.start_excluded or other.start_excluded

        end, end_excluded = min(
            (self.end, self.end_excluded), (other.end, other.end_excluded)
        )
        if self.end == other.end:
            end_excluded = self.end_excluded or other.end_excluded

        return Interval(
            start, end, start_excluded=start_excluded, end_excluded=end_excluded
        )

    def __repr__(self) -> str:
        return f"{'(' if self.start_excluded else '['}{self.start}, {self.end}{')' if self.end_excluded else ']'}"

    def __add__(self, value: int | float) -> Interval:
        return Interval(
            self.start + value, self.end + value, self.start_excluded, self.end_excluded
        )

    def __sub__(self, value: int | float) -> Interval:
        return Interval(
            self.start - value, self.end - value, self.start_excluded, self.end_excluded
        )

    def iter_integers(self) -> typing.Iterable[int]:
        """Iterate over all the integers strictly contained in ``self``."""
        inclusive_start_int = int(math.ceil(self.start))
        if self.start_excluded and abs(self.start - round(self.start)) < 1e-30:
            inclusive_start_int += 1
        exclusive_end_int = int(math.ceil(self.end))
        if not self.end_excluded and abs(self.end - round(self.end)) < 1e-30:
            exclusive_end_int += 1
        return range(inclusive_start_int, exclusive_end_int)


EMPTY_INTERVAL = Interval(0, 0, start_excluded=True, end_excluded=True)
R_interval = Interval(
    float("-inf"), float("inf"), start_excluded=True, end_excluded=True
)
Rplus_interval = Interval(0, float("inf"), start_excluded=False, end_excluded=True)
