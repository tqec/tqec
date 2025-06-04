from __future__ import annotations

from enum import Flag, auto
from typing import Iterator


class SpatialArms(Flag):
    NONE = 0
    UP = auto()
    RIGHT = auto()
    DOWN = auto()
    LEFT = auto()

    @classmethod
    def get_map_from_arm_to_shift(cls) -> dict[SpatialArms, tuple[int, int]]:
        return {
            cls.UP: (0, -1),
            cls.RIGHT: (1, 0),
            cls.DOWN: (0, 1),
            cls.LEFT: (-1, 0),
        }

    @staticmethod
    def I_shaped_arms() -> list[SpatialArms]:
        return [
            SpatialArms.DOWN | SpatialArms.UP,
            SpatialArms.LEFT | SpatialArms.RIGHT,
        ]

    @staticmethod
    def L_shaped_arms() -> list[SpatialArms]:
        return [
            SpatialArms.DOWN | SpatialArms.LEFT,
            SpatialArms.DOWN | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.LEFT,
            SpatialArms.UP | SpatialArms.RIGHT,
        ]

    @staticmethod
    def T_shaped_arms() -> list[SpatialArms]:
        return [
            SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP,
            SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN,
            SpatialArms.RIGHT | SpatialArms.DOWN | SpatialArms.LEFT,
        ]

    @staticmethod
    def X_shaped_arms() -> list[SpatialArms]:
        return [SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT]

    @staticmethod
    def single_arms() -> list[SpatialArms]:
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
