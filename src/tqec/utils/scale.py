"""Defines several scalable classes such as :class:`LinearFunction` or :class:`Scalable2D`.

This module defines the necessary classes to help with scalable structures.
:class:`LinearFunction` simply represents a linear function ``a * k + b`` where
``a`` and ``b`` are floating-point quantities.

This :class:`LinearFunction` class is for example used to represent the shape
of a :class:`~tqec.templates.base.Template` for any input value ``k``.
More specifically, :class:`~tqec.templates.qubit.QubitTemplate` has a
shape that should exactly match a pair of ``LinearFunction(2, 2)`` which is
basically ``2k + 2``.

:class:`Scalable2D` is exactly made to represent such pairs of scalable quantities.

"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from typing_extensions import Self

from tqec.circuit.qubit import GridQubit
from tqec.utils.exceptions import TQECError
from tqec.utils.position import PhysicalQubitShape2D, PlaquetteShape2D, Shape2D, Shift2D


@dataclass(frozen=True)
class LinearFunction:
    """Represent a linear function.

    A linear function is fully described with a slope and an offset.

    """

    slope: float = 1.0
    offset: float = 0.0

    def __call__(self, x: float) -> float:
        """Evaluate the linear function on a given input.

        Args:
            x: the input to evaluate the linear function on.

        Returns:
            the image of x.

        """
        return self.slope * x + self.offset

    def __add__(self, other: LinearFunction | int | float) -> LinearFunction:
        """Add two linear functions and returns the result.

        This method does not modify self in-place.

        Args:
            other: the right-hand side to add to self.

        Returns:
            a new linear function instance representing `self + other`.

        """
        if isinstance(other, (int, float)):
            other = LinearFunction(0, other)
        return LinearFunction(self.slope + other.slope, self.offset + other.offset)

    def __sub__(self, other: LinearFunction | int | float) -> LinearFunction:
        """Subtract two linear functions and returns the result.

        This method does not modify self in-place.

        Args:
            other: the right-hand side to subtract to self.

        Returns:
            a new linear function instance representing `self - other`.

        """
        if isinstance(other, (int, float)):
            other = LinearFunction(0, other)
        return LinearFunction(self.slope - other.slope, self.offset - other.offset)

    def __mul__(self, other: int | float) -> LinearFunction:
        """Multiply a linear function by a scalar.

        Args:
            other: the scalar that should multiply self.

        Returns:
            a copy of `self`, scaled by the provided `other`.

        """
        return self.__rmul__(other)

    def __rmul__(self, other: int | float) -> LinearFunction:
        """Multiply a linear function by a scalar.

        Args:
            other: the scalar that should multiply self.

        Returns:
            a copy of `self`, scaled by the provided `other`.

        """
        return LinearFunction(other * self.slope, other * self.offset)

    def intersection(self, other: LinearFunction) -> float | None:
        """Compute the intersection between two linear functions.

        Args:
            other: the `LinearFunction` instance to intersect with `self`.

        Returns:
            If they intersect, return x such that `self(x) = other(x)`.
            Otherwise, return None.

        """
        if self.slope == other.slope:
            return None

        return -(other.offset - self.offset) / (other.slope - self.slope)

    @staticmethod
    def _from(obj: LinearFunction | float) -> LinearFunction:  # pragma: no cover
        if isinstance(obj, (float, int)):
            return LinearFunction(0, obj)
        else:
            return obj

    def __repr__(self) -> str:
        if abs(self.slope) < 1e-8:
            return str(self.offset)
        if abs(self.offset) < 1e-8:
            return f"{self.slope}*x"
        return f"{self.slope}*x + {self.offset}"

    def integer_eval(self, x: int) -> int:
        """Evaluate the linear function on ``x`` and return the result as an integer.

        Raises:
            TQECError: if the result is not an integer.

        Returns:
            ``int(self(x))``.

        """
        return round_or_fail(self.slope * x + self.offset)

    def exact_integer_div(self, div: int) -> LinearFunction:
        """Divide ``self`` by ``div`` when possible.

        Raises:
            ZeroDivisionError: if ``div == 0``.
            TQECError: if ``self.slope`` or ``self.offset`` are not divisible by ``div``.

        Returns:
            a new linear function such that ``div * ret == self``.

        """
        if div == 0:
            raise ZeroDivisionError()
        slope, offset = round_or_fail(self.slope), round_or_fail(self.offset)
        if slope % div != 0:
            raise TQECError(
                "Trying to divide exactly a LinearFunction by an integer that "
                f"is not a multiple of the slope. Divisor: {div}. Slope: {slope}."
            )
        if offset % div != 0:
            raise TQECError(
                "Trying to divide exactly a LinearFunction by an integer that "
                f"is not a multiple of the offset. Divisor: {div}. Offset: "
                f"{offset}."
            )
        return LinearFunction(slope // div, offset // div)

    def is_constant(self, atol: float = 1e-8) -> bool:
        """Return ``True`` if ``self.slope`` is close to ``0``."""
        return abs(self.slope) < atol

    def is_scalable(self, atol: float = 1e-8) -> bool:
        """Return ``True`` if ``not self.is_scalable``."""
        return not self.is_constant(atol)

    def is_close_to(self, other: LinearFunction, atol: float = 1e-8) -> bool:
        """Return ``True`` is ``self`` is approximately equal to ``other``."""
        return abs(self.slope - other.slope) < atol and abs(self.offset - other.offset) < atol

    @staticmethod
    def unambiguous_max_on_positives(
        fs: Iterable[LinearFunction], default: LinearFunction | None = None
    ) -> LinearFunction:
        """Compute the unambiguous maximum of the provided linear functions on the positive numbers.

        A unambiguous maximum on R+ (the set of positive numbers) is a linear
        function that is greater or equal than all the functions in ``fs`` on
        the whole R+ interval.

        Args:
            fs: linear functions to find a unambiguous maximum in.
            default: default value to return if ``fs`` is empty. Defaults to
                ``None`` which is internally translated to ``LinearFunction(0, 0)``.

        Raises:
            TQECError: if the maximum found is ambiguous.

        Returns:
            the unambiguous maximum in ``fs``.

        """
        if default is None:
            default = LinearFunction(0, 0)
        iterator = iter(fs)
        try:
            res: LinearFunction = next(iterator)
        except StopIteration:
            return default
        # Find the **potentially ambiguous** maximum trivially.
        # If the maximum is unambiguous, res will be it. Else, there is an
        # ambiguity and so we should raise.
        for f in iterator:
            if f.offset >= res.offset and f.slope >= res.slope:
                res = f

        for f in fs:
            if f.offset > res.offset or f.slope > res.slope:
                raise TQECError(
                    "Could not find a unambiguous maximum in the provided linear functions. "
                    f"{res} could be the maximum, but is ambiguous with {f}."
                )
        return res

    @staticmethod
    def safe_mul(lhs: LinearFunction, rhs: LinearFunction) -> LinearFunction:
        """Return ``lhs * rhs``, checking that the result is a linear function.

        Raises:
            TQECError: if both ``lhs.slope`` and ``rhs.slope`` are non-zero.

        """
        if lhs.slope != 0 and rhs.slope != 0:
            raise TQECError(f"The result of ({lhs}) * ({rhs}) is not a linear function.")
        return LinearFunction(
            lhs.slope * rhs.offset + rhs.slope * lhs.offset, lhs.offset * rhs.offset
        )


def round_or_fail(f: float, atol: float = 1e-8) -> int:
    """Try to round the provided ``f`` to the nearest integer.

    Args:
        f: a floating-point value that should be close (absolute tolerance of
            ``atol``) to its nearest integer number.
        atol: absolute tolerance between the provided ``f`` and ``round(f)`` that
            is acceptable.

    Raises:
        TQECError: if ``abs(f - round(f)) > atol``

    Returns:
        ``int(round(f))``

    """
    rounded_value = round(f)
    if abs(f - rounded_value) > atol:
        raise TQECError(f"Rounding from {f} to integer failed.")
    return rounded_value


@dataclass(frozen=True)
class Scalable2D:
    """A pair of scalable quantities.

    Attributes:
        x: a linear function representing the value of the ``x`` coordinate.
        y: a linear function representing the value of the ``y`` coordinate.

    """

    x: LinearFunction
    y: LinearFunction

    def to_shape_2d(self, k: int) -> Shape2D:
        """Get the represented value for a given scaling parameter ``k``.

        Args:
            k: scaling parameter to use to get a value from the scalable
                quantities stored in ``self``.

        Raises:
            TQECError: if any of ``self.x(k)`` or ``self.y(k)`` returns a
                number that is not an integer (or very close to an integer).

        Returns:
            ``Shape2D(self.x.integer_eval(k), self.y.integer_eval(k))``

        """
        return Shape2D(self.x.integer_eval(k), self.y.integer_eval(k))

    def to_numpy_shape(self, k: int) -> tuple[int, int]:
        """Get a tuple of coordinates in ``numpy``-coordinates.

        Raises:
            TQECError: if any of ``self.x(k)`` or ``self.y(k)`` returns a
                number that is not an integer (or very close to an integer).

        Returns:
            a tuple of coordinates in ``numpy``-coordinates.

        """
        return self.to_shape_2d(k).to_numpy_shape()

    @staticmethod
    def _get_x_y(
        other: Scalable2D | Shift2D | tuple[LinearFunction | int, LinearFunction | int],
    ) -> tuple[LinearFunction | int, LinearFunction | int]:
        if isinstance(other, tuple):
            return cast(tuple[LinearFunction | int, LinearFunction | int], other)
        elif isinstance(other, (Scalable2D, Shift2D)):
            return other.x, other.y
        else:
            # added because flagged by ty
            raise TypeError("Unsupported input provided.")

    def __add__(self: Self, other: Self | Shift2D | tuple[int, int]) -> Self:
        x, y = Scalable2D._get_x_y(other)
        return cast(Self, self.__class__(self.x + x, self.y + y))

    def __sub__(self: Self, other: Self | Shift2D | tuple[int, int]) -> Self:
        x, y = Scalable2D._get_x_y(other)
        return cast(Self, self.__class__(self.x - x, self.y - y))


class PlaquetteScalable2D(Scalable2D):
    """A pair of scalable quantities in plaquette coordinates."""

    def to_shape_2d(self, k: int) -> PlaquetteShape2D:
        """Evaluate both coordinates with ``k`` as input."""
        return PlaquetteShape2D(self.x.integer_eval(k), self.y.integer_eval(k))

    def __mul__(self, other: Shift2D) -> PhysicalQubitScalable2D:
        return PhysicalQubitScalable2D(self.x * other.x, self.y * other.y)


class PhysicalQubitScalable2D(Scalable2D):
    """A pair of scalable quantities in physical qubit coordinates."""

    def to_shape_2d(self, k: int) -> PhysicalQubitShape2D:
        """Evaluate both coordinates with ``k`` as input."""
        return PhysicalQubitShape2D(self.x.integer_eval(k), self.y.integer_eval(k))

    def to_grid_qubit(self, k: int) -> GridQubit:
        """Evaluate both coordinates with ``k`` as input, returning a :class:`.GridQubit`."""
        return GridQubit(self.x.integer_eval(k), self.y.integer_eval(k))
