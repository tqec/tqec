from __future__ import annotations

from enum import Flag, auto


class JunctionArms(Flag):
    NONE = 0
    UP = auto()
    RIGHT = auto()
    DOWN = auto()
    LEFT = auto()

    @classmethod
    def get_map_from_arm_to_shift(cls) -> dict[JunctionArms, tuple[int, int]]:
        return {
            cls.UP: (0, 1),
            cls.RIGHT: (1, 0),
            cls.DOWN: (0, -1),
            cls.LEFT: (-1, 0),
        }

    @staticmethod
    def I_shaped_arms() -> list[JunctionArms]:
        return [
            JunctionArms.DOWN | JunctionArms.UP,
            JunctionArms.LEFT | JunctionArms.RIGHT,
        ]

    @staticmethod
    def L_shaped_arms() -> list[JunctionArms]:
        return [
            JunctionArms.DOWN | JunctionArms.LEFT,
            JunctionArms.DOWN | JunctionArms.RIGHT,
            JunctionArms.UP | JunctionArms.LEFT,
            JunctionArms.UP | JunctionArms.RIGHT,
        ]

    @staticmethod
    def T_shaped_arms() -> list[JunctionArms]:
        return [
            JunctionArms.DOWN | JunctionArms.LEFT | JunctionArms.UP,
            JunctionArms.LEFT | JunctionArms.UP | JunctionArms.RIGHT,
            JunctionArms.UP | JunctionArms.RIGHT | JunctionArms.DOWN,
            JunctionArms.RIGHT | JunctionArms.DOWN | JunctionArms.LEFT,
        ]

    @staticmethod
    def X_shaped_arms() -> list[JunctionArms]:
        return [
            JunctionArms.DOWN | JunctionArms.LEFT | JunctionArms.UP | JunctionArms.RIGHT
        ]

    @staticmethod
    def single_arms() -> list[JunctionArms]:
        return [
            JunctionArms.UP,
            JunctionArms.RIGHT,
            JunctionArms.DOWN,
            JunctionArms.LEFT,
        ]

    def __len__(self):
        return sum(arm in self for arm in JunctionArms.single_arms())

    def __iter__(self):
        return [arm for arm in JunctionArms.single_arms() if arm in self]
