from __future__ import annotations

from collections.abc import Iterator
from enum import Flag, auto

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube
from tqec.utils.exceptions import TQECError


class SpatialArms(Flag):
    NONE = 0
    UP = auto()
    RIGHT = auto()
    DOWN = auto()
    LEFT = auto()

    @staticmethod
    def from_cube_in_graph(cube: Cube, graph: BlockGraph) -> SpatialArms:
        """Return the spatial arms of a cube in a block graph."""
        if not cube.is_spatial:
            return SpatialArms.NONE  # pragma: no cover
        pos = cube.position
        if pos not in graph or graph[pos] != cube:
            raise TQECError(f"Cube {cube} is not in the graph.")
        spatial_arms = SpatialArms.NONE
        for flag, shift in SpatialArms.get_map_from_arm_to_shift().items():
            if graph.has_pipe_between(pos, pos.shift_by(*shift)):
                spatial_arms |= flag
        return spatial_arms

    @property
    def has_spatial_arm_in_both_dimensions(self) -> bool:
        """Checks if the spatial arms have arms in both spatial dimensions."""
        return (SpatialArms.DOWN in self or SpatialArms.UP in self) and (
            SpatialArms.LEFT in self or SpatialArms.RIGHT in self
        )

    @classmethod
    def get_map_from_arm_to_shift(cls) -> dict[SpatialArms, tuple[int, int]]:
        """Return a mapping from any single arm to 2-dimensional shifts.

        The returned shifts are the shift needed to get the cube at the other end of the associated
        single arm.

        If a block ``B`` has a LEFT arm, the other end of the arm is the coordinates of ``B``
        shifted by ``(-1, 0)``. Hence,
        ``SpatialArms.get_map_from_arm_to_shift()[SpatialArms.LEFT] == (-1 0)``.

        Warning:
            In TQEC convention, the ``Y`` axis is pointing **downwards**. That means that UP is
            linked to ``(0, -1)`` in the returned dictionary.

        Returns:
            a mapping from any single arm to the shift needed to get the cube at the other end of
            that arm.

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
        return [  # pragma: no cover
            SpatialArms.DOWN | SpatialArms.LEFT,
            SpatialArms.DOWN | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.LEFT,
            SpatialArms.UP | SpatialArms.RIGHT,
        ]

    @staticmethod
    def T_shaped_arms() -> list[SpatialArms]:
        """Return the 4 arm combinations that form a T-shape."""
        return [  # pragma: no cover
            SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP,
            SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT,
            SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN,
            SpatialArms.RIGHT | SpatialArms.DOWN | SpatialArms.LEFT,
        ]

    @staticmethod
    def X_shaped_arms() -> list[SpatialArms]:
        """Return the only arm combinations that form a X-shape (i.e., all the arms)."""
        return [  # pragma: no cover
            SpatialArms.DOWN | SpatialArms.LEFT | SpatialArms.UP | SpatialArms.RIGHT
        ]

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
        yield from (arm for arm in SpatialArms.single_arms() if arm in self)  # pragma: no cover

    def __repr__(self) -> str:
        if self == SpatialArms.NONE:
            return f"{SpatialArms.__name__}.NONE"
        return " | ".join(f"{SpatialArms.__name__}.{arm.name}" for arm in self)
