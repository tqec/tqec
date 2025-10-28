"""Defines 2D and 3D data-structures storing vectors of integers.

This module defines several classes to store pairs (2D) or 3-tuples (3D) of
integers representing coordinates. They are used all over the code base to avoid
any coordinate system mess and to explicitly annotate each coordinate with its
significance. Basically, instead of having

.. code-block:: python

    coords = (0, 4)  # Is it (y, x) or (x, y)?
    # 0 used below, but if the coords tuple was obtained from a call to
    # `.shape` from a numpy array it should rather be a 1.
    x = coords[0]

we have

.. code-block:: python

    coords = Position2D(0, 4)
    x = coords.x

This is particularly useful when we, as humans, are mostly used to always have
(x, y) coordinates but some libraries (such as numpy) reverse that order for
indexing.

"""

from __future__ import annotations

import re
from dataclasses import astuple, dataclass
from enum import Enum
from typing import cast

import numpy as np
import numpy.typing as npt
from typing_extensions import Self

from tqec.utils.exceptions import TQECError


@dataclass(frozen=True, order=True)
class Vec2D:
    x: int
    y: int


@dataclass(frozen=True, order=True)
class Vec3D:
    x: int
    y: int
    z: int


class Position2D(Vec2D):
    """Represent a position on a 2-dimensional plane.

    Warning:
        This class represents a position without any knowledge of the coordinate
        system being used. As such, it should only be used when the coordinate
        system is meaningless or in localised places where the coordinate system
        is obvious. In particular, this class should be avoided in interfaces.

    """

    def with_block_coordinate_system(self) -> BlockPosition2D:
        """Return a :class:`.BlockPosition2D` from ``self``."""
        return BlockPosition2D(self.x, self.y)  # pragma: no cover

    def is_neighbour(self, other: Position2D) -> bool:
        """Check if the other position is near to this position, i.e. Manhattan distance is 1."""
        return abs(self.x - other.x) + abs(self.y - other.y) == 1

    def to_3d(self, z: int = 0) -> Position3D:
        """Get a 3-dimensional position with the ``x`` and ``y`` coordinates from ``self``."""
        return Position3D(self.x, self.y, z)


class PhysicalQubitPosition2D(Position2D):
    """Represent the position of a physical qubit on a 2-dimensional plane."""


class PlaquettePosition2D(Position2D):
    """Represent the position of a plaquette on a 2-dimensional plane."""

    def get_origin_position(self, shift: Shift2D) -> PhysicalQubitPosition2D:
        """Return the position of the plaquette origin."""
        return PhysicalQubitPosition2D(shift.x * self.x, shift.y * self.y)  # pragma: no cover


class BlockPosition2D(Position2D):
    """Represent the position of a block on a 2-dimensional plane."""

    def get_top_left_plaquette_position(self, block_shape: PlaquetteShape2D) -> PlaquettePosition2D:
        """Return the position of the top-left plaquette of the block."""
        return PlaquettePosition2D(block_shape.x * self.x, block_shape.y * self.y)


class Shape2D(Vec2D):
    def to_numpy_shape(self) -> tuple[int, int]:
        """Return the shape according to numpy indexing.

        In the coordinate system used in this library, numpy indexes arrays using (y, x)
        coordinates. This method is here to translate a Shape instance to a numpy shape
        transparently for the user.

        In the coordinate system used in this library, numpy indexes arrays using (y, x)
        coordinates. This method is here to translate a ``Shape`` instance to a numpy shape
        transparently for the user.

        """
        return (self.y, self.x)


class PlaquetteShape2D(Shape2D):
    """Represent a 2-dimensional shape using plaquette coordinate system."""


class PhysicalQubitShape2D(Shape2D):
    """Represent a 2-dimensional shape using physical qubit coordinate system."""


class Shift2D(Vec2D):
    def __mul__(self, factor: int) -> Shift2D:
        return Shift2D(factor * self.x, factor * self.y)  # pragma: no cover

    def __rmul__(self, factor: int) -> Shift2D:
        return self.__mul__(factor)  # pragma: no cover


class Position3D(Vec3D):
    """A 3D integer position."""

    x: int
    y: int
    z: int

    def shift_by(self, dx: int = 0, dy: int = 0, dz: int = 0) -> Self:
        """Shift the position by the given offset."""
        return cast(Self, self.__class__(self.x + dx, self.y + dy, self.z + dz))

    def shift_in_direction(self, direction: Direction3D, shift: int) -> Self:
        """Shift the position in the given direction by the given shift."""
        if direction == Direction3D.X:
            return self.shift_by(dx=shift)
        elif direction == Direction3D.Y:
            return self.shift_by(dy=shift)
        else:
            return self.shift_by(dz=shift)

    def is_neighbour(self, other: Position3D) -> bool:
        """Check if the other position is near to this position, i.e. Manhattan distance is 1."""
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z) == 1

    def as_tuple(self) -> tuple[int, int, int]:
        """Return the position as a tuple."""
        return astuple(self)

    def __str__(self) -> str:
        return f"({self.x},{self.y},{self.z})"

    def as_2d(self) -> Position2D:
        """Return the position as a 2D position."""
        return Position2D(self.x, self.y)


class BlockPosition3D(Position3D):
    """Represent the position of a block in 3D space."""

    def as_2d(self) -> BlockPosition2D:
        """Return ``self`` as a 2-dimensional position, ignoring the ``z`` coordinate."""
        return BlockPosition2D(self.x, self.y)


class Direction3D(Enum):
    """Axis directions in the 3D spacetime diagram."""

    X = 0
    Y = 1
    Z = 2

    @staticmethod
    def all_directions() -> list[Direction3D]:
        """Return all the directions."""
        return [Direction3D.X, Direction3D.Y, Direction3D.Z]

    @staticmethod
    def spatial_directions() -> list[Direction3D]:
        """Return all the spatial directions."""
        return [Direction3D.X, Direction3D.Y]

    @staticmethod
    def temporal_directions() -> list[Direction3D]:
        """Return all the temporal directions."""
        return [Direction3D.Z]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_neighbouring_positions(source: Position3D, sink: Position3D) -> Direction3D:
        """Return the direction to go from ``source`` to ``sink``."""
        assert source.is_neighbour(sink)
        for direction, (source_coord, sink_coord) in zip(
            Direction3D.all_directions(), zip(source.as_tuple(), sink.as_tuple())
        ):
            if source_coord != sink_coord:
                return direction
        raise TQECError(
            f"Could not find the direction from two neighbouring positions {source:=} and {sink:=}."
        )

    @property
    def orthogonal_directions(self) -> tuple[Direction3D, Direction3D]:
        """Return the two directions orthogonal to ``self``."""
        i = self.value
        return Direction3D((i + 1) % 3), Direction3D((i + 2) % 3)


@dataclass(frozen=True)
class SignedDirection3D:
    """Signed directions in the 3D spacetime diagram."""

    direction: Direction3D
    towards_positive: bool

    def __neg__(self) -> SignedDirection3D:
        return SignedDirection3D(self.direction, not self.towards_positive)

    def __str__(self) -> str:
        return f"{'+' if self.towards_positive else '-'}{self.direction}"

    @staticmethod
    def from_string(s: str) -> SignedDirection3D:
        """Return the signed direction from a string.

        Args:
            s: The string representation of the signed direction. The string
                should have the format "<sign><direction>", where "<direction>"
                is one of "X", "Y", "Z" and "<sign>" is either "+" or "-".

        Returns:
            The signed direction.

        Raises:
            TQECError: If the string does not match the expected format.

        """
        match = re.match(r"([+-])([XYZ])", s)
        if match is None:
            raise TQECError(f"Invalid signed direction: {s}, expected format: [+/-][XYZ]")
        sign, direction = match.groups()
        return SignedDirection3D(Direction3D("XYZ".index(direction)), sign == "+")


@dataclass(frozen=True, order=True)
class FloatPosition3D:
    """A 3D float position."""

    x: float
    y: float
    z: float

    def shift_by(self, dx: float = 0, dy: float = 0, dz: float = 0) -> FloatPosition3D:
        """Shift the position by the given offset."""
        return FloatPosition3D(self.x + dx, self.y + dy, self.z + dz)

    def shift_in_direction(self, direction: Direction3D, shift: float) -> FloatPosition3D:
        """Shift the position in the given direction by the given shift."""
        if direction == Direction3D.X:
            return self.shift_by(dx=shift)
        elif direction == Direction3D.Y:
            return self.shift_by(dy=shift)
        else:
            return self.shift_by(dz=shift)

    def as_array(self) -> npt.NDArray[np.float32]:
        """Return the position as a numpy array."""
        return np.asarray(astuple(self), dtype=np.float32)
