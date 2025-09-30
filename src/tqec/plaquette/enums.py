from __future__ import annotations

from enum import Enum, auto


class PlaquetteOrientation(Enum):
    RIGHT = auto()
    LEFT = auto()
    DOWN = auto()
    UP = auto()

    def to_plaquette_side(self) -> PlaquetteSide:
        """Return the plaquette side corresponding to ``self``.

        If ``self == PlaquetteOrientation.RIGHT`` then
        ``self.to_plaquette_side() == PlaquetteSide.LEFT`` because a plaquette oriented to the right
        has 2 data-qubit on its left side.

        """
        if self == PlaquetteOrientation.RIGHT:
            return PlaquetteSide.LEFT
        elif self == PlaquetteOrientation.LEFT:
            return PlaquetteSide.RIGHT
        elif self == PlaquetteOrientation.DOWN:
            return PlaquetteSide.UP
        else:  # if self == PlaquetteOrientation.UP:
            return PlaquetteSide.DOWN


class PlaquetteSide(Enum):
    RIGHT = auto()
    LEFT = auto()
    DOWN = auto()
    UP = auto()

    def opposite(self) -> PlaquetteSide:
        """Return the opposite side."""
        if self == PlaquetteSide.RIGHT:
            return PlaquetteSide.LEFT
        elif self == PlaquetteSide.LEFT:
            return PlaquetteSide.RIGHT
        elif self == PlaquetteSide.DOWN:
            return PlaquetteSide.UP
        else:
            return PlaquetteSide.DOWN
