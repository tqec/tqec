from __future__ import annotations

from collections.abc import Iterator
from enum import Flag, auto


class SpatialArms(Flag):
    NONE = 0
    UP = auto()
    RIGHT = auto()
    DOWN = auto()
    LEFT = auto()

    @classmethod
    def get_map_from_arm_to_shift(cls) -> dict[SpatialArms, tuple[int, int]]:
        """Return a mapping from any **single** arm to the shift needed to get the cube at the other
        end of that arm.

        If a block ``B`` has a LEFT arm, the other end of the arm is the coordinates of ``B``
        shifted by ``(-1, 0)``. Hence,
        ``SpatialArms.get_map_from_arm_to_shift()[SpatialArms.LEFT] == (-1 0)``.

        Warning:
            In TQEC convention, the ``Y`` axis is pointing **downwards**. That means that UP is
            linked to ``(0, -1)`` in the returned dictionary.

        """
        return {
            cls.UP: (0, -1),
            cls.RIGHT: (1, 0),
            cls.DOWN: (0, 1),
            cls.LEFT: (-1, 0),
        }

    @staticmethod
    def I_shaped_arms() -> list[SpatialArms]:
        """Return the 2 arm combinations that form a I-shape.

        The 2 combinations are UP | DOWN and LEFT | RIGHT.
        """
        return [
            SpatialArms.DOWN | SpatialArms.UP,
            SpatialArms.LEFT | SpatialArms.RIGHT,
        ]

    @staticmethod
    def L_shaped_arms() -> list[SpatialArms]:
        """Return the 4 arm combinations that form a L-shape.

        The 4 combinations are DOWN | LEFT, DOWN | RIGHT, UP | LEFT and UP | RIGHT.
        """
        return [
            SpatialArms.DOWN | SpatialArms.LEFT,
            SpatialArms.DOWN | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.LEFT,
            SpatialArms.UP | SpatialArms.RIGHT,
        ]

    @staticmethod
    def T_shaped_arms() -> list[SpatialArms]:
        """Return the 4 arm combinations that form a T-shape."""
        return [
            SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP,
            SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN,
            SpatialArms.RIGHT | SpatialArms.DOWN | SpatialArms.LEFT,
        ]

    @staticmethod
    def X_shaped_arms() -> list[SpatialArms]:
        """Return the only arm combinations that form a X-shape (i.e., all the arms)."""
        return [SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT]

    @staticmethod
    def single_arms() -> list[SpatialArms]:
        """Return the 4 possible single arms."""
        return [
            SpatialArms.UP,
            SpatialArms.RIGHT,
            SpatialArms.DOWN,
            SpatialArms.LEFT,
        ]

    def __len__(self) -> int:
        return sum(arm in self for arm in SpatialArms.single_arms())

    def __iter__(self) -> Iterator[SpatialArms]:
        yield from (arm for arm in SpatialArms.single_arms() if arm in self)

    def __repr__(self) -> str:
        if self == SpatialArms.NONE:
            return f"{SpatialArms.__name__}.NONE"
        return " | ".join(f"{SpatialArms.__name__}.{arm.name}" for arm in self)
