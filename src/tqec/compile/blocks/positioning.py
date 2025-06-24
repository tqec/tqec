from __future__ import annotations

from abc import ABC
from typing import Generic

from typing_extensions import Self, TypeVar

from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition2D, BlockPosition3D, SignedDirection3D


class LayoutPosition2D(ABC):
    def __init__(self, x: int, y: int) -> None:
        """Internal class to represent the local indexing used to represent both
        cubes and pipes.

        Args:
            x: first coordinate.
            y: second coordinate.

        """
        super().__init__()
        self._x = x
        self._y = y

    @staticmethod
    def from_block_position(pos: BlockPosition2D) -> LayoutCubePosition2D:
        return LayoutCubePosition2D(2 * pos.x, 2 * pos.y)

    @staticmethod
    def from_pipe_position(
        pipe_position: tuple[BlockPosition2D, BlockPosition2D],
    ) -> LayoutPipePosition2D:
        u, v = sorted(pipe_position)
        assert u.is_neighbour(v)
        assert u < v
        return LayoutPipePosition2D(2 * u.x + (u.x != v.x), 2 * u.y + (u.y != v.y))

    def __hash__(self) -> int:
        return hash((self._x, self._y))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LayoutPosition2D) and self._x == other._x and self._y == other._y

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(x={self._x},y={self._y})"

    def __add__(self, other: Self | tuple[int, int]) -> Self:
        if isinstance(other, tuple):
            x, y = other
            return self.__class__(self._x + x, self._y + y)
        return self.__class__(self._x + other._x, self._y + other._y)


class LayoutCubePosition2D(LayoutPosition2D):
    def __init__(self, x: int, y: int) -> None:
        """Internal class to represent the position of a cube on the grid.

        For the moment, only 2 entities have to appear on the grid: cubes and pipes.
        For that reason, we define cube positions (i.e., :class:`LayoutCubePosition2D`
        instances) to be on even coordinates and pipes positions to have one odd
        coordinates in the pipe dimension and even coordinates elsewhere.
        """
        if (x % 2 == 1) or (y % 2 == 1):
            clsname = self.__class__.__name__
            raise TQECException(f"{clsname} cannot contain any odd coordinate.")
        super().__init__(x, y)

    def to_block_position(self) -> BlockPosition2D:
        return BlockPosition2D(self._x // 2, self._y // 2)


class LayoutPipePosition2D(LayoutPosition2D):
    def __init__(self, x: int, y: int) -> None:
        """Internal class to represent the position of a cube on the grid.

        For the moment, only 2 entities have to appear on the grid: cubes and pipes.
        For that reason, we define cube positions (i.e., :class:`LayoutCubePosition2D`
        instances) to be on even coordinates and pipes positions to have one odd
        coordinates in the pipe dimension and even coordinates elsewhere.
        """
        if not ((x % 2 == 1) ^ (y % 2 == 1)):
            clsname = self.__class__.__name__
            raise TQECException(f"{clsname} should contain one odd and one even coordinate.")
        super().__init__(x, y)

    def to_pipe(self) -> tuple[BlockPosition2D, BlockPosition2D]:
        if self._x % 2 == 1:
            return BlockPosition2D((self._x - 1) // 2, self._y // 2), BlockPosition2D(
                (self._x + 1) // 2, self._y // 2
            )
        return BlockPosition2D(self._x // 2, (self._y - 1) // 2), BlockPosition2D(
            self._x // 2, (self._y + 1) // 2
        )


T = TypeVar("T", bound=LayoutPosition2D, covariant=True, default=LayoutPosition2D)


class LayoutPosition3D(ABC, Generic[T]):
    def __init__(self, spatial_position: T, z: int) -> None:
        """Internal class to represent the local indexing used to represent both
        cubes and pipes in 3-dimensions.

        This class simply wraps a :class:`LayoutPosition2D` instance with an
        integer-valued z coordinate.

        Because temporal pipes are "absorbed" in its neighbouring blocks, we do not
        have to represent them, hence the z coordinate does not need any kind of
        special treatment like the x and y coordinates.
        """
        super().__init__()
        self._spatial_position = spatial_position
        self._z = z

    @staticmethod
    def from_block_position(
        pos: BlockPosition3D,
    ) -> LayoutPosition3D[LayoutCubePosition2D]:
        return LayoutPosition3D(LayoutCubePosition2D.from_block_position(pos.as_2d()), pos.z)

    @staticmethod
    def from_pipe_position(
        pipe_position: tuple[BlockPosition3D, BlockPosition3D],
    ) -> LayoutPosition3D[LayoutPipePosition2D]:
        u, v = sorted(pipe_position)
        assert u.is_neighbour(v)
        assert u < v
        return LayoutPosition3D(LayoutPosition2D.from_pipe_position((u.as_2d(), v.as_2d())), u.z)

    @staticmethod
    def from_block_and_signed_direction(
        pos: BlockPosition3D, dir: SignedDirection3D
    ) -> LayoutPosition3D[LayoutPipePosition2D]:
        neighbour = pos.shift_in_direction(dir.direction, 1 if dir.towards_positive else -1)
        u, v = sorted((pos, neighbour))
        assert u.is_neighbour(v)
        return LayoutPosition3D(LayoutPosition2D.from_pipe_position((u.as_2d(), v.as_2d())), u.z)

    def __hash__(self) -> int:
        return hash((self._spatial_position, self._z))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, LayoutPosition3D)
            and self._spatial_position == other._spatial_position
            and self._z == other._z
        )

    def as_2d(self) -> LayoutPosition2D:
        return self._spatial_position

    @property
    def z(self) -> int:
        return self._z

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(spatial_position={self._spatial_position},z={self._z})"
