from __future__ import annotations

from abc import ABC, abstractmethod
from math import ceil
from typing import Generic

from typing_extensions import Self, TypeVar, override

from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition2D, BlockPosition3D
from tqec.utils.scale import PhysicalQubitScalable2D


class LayoutPosition2D(ABC):
    """Internal class to represent the local indexing used to represent both
    cubes and pipes."""

    def __init__(self, x: int, y: int) -> None:
        super().__init__()
        self._x = x
        self._y = y

    @staticmethod
    def from_block_position(pos: BlockPosition2D) -> LayoutCubePosition2D:
        return LayoutCubePosition2D(2 * pos.x, 2 * pos.y)

    @staticmethod
    def from_junction_position(
        junction_position: tuple[BlockPosition2D, BlockPosition2D],
    ) -> LayoutPipePosition2D:
        u, v = sorted(junction_position)
        assert u.is_neighbour(v)
        assert u < v
        return LayoutPipePosition2D(2 * u.x + (u.x != v.x), 2 * u.y + (u.y != v.y))

    @abstractmethod
    def origin_qubit(
        self, element_shape: PhysicalQubitScalable2D, border_size: int
    ) -> PhysicalQubitScalable2D:
        """Returns the origin qubit of the position.

        By convention:

        - the origin of a cube is its top-left qubit, **borders included**,
        - the origin of a pipe is its top-left qubit.

        Args:
            element_shape: scalable qubit shape of the cubes composing the grid.
                In other words, scalable shape of a logical qubit.
            border_size: size of what should be considered to be the "border"
                around grid elements. For regular surface code, this should be 2
                as "removing" the plaquettes on the borders "trims" all the
                operations on 2 qubits.
        """
        pass

    def __hash__(self) -> int:
        return hash((self._x, self._y))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, LayoutPosition2D)
            and self._x == other._x
            and self._y == other._y
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(x={self._x},y={self._y})"

    def __add__(self, other: Self | tuple[int, int]) -> Self:
        if isinstance(other, tuple):
            x, y = other
            return self.__class__(self._x + x, self._y + y)
        return self.__class__(self._x + other._x, self._y + other._y)


class LayoutCubePosition2D(LayoutPosition2D):
    """Internal class to represent the position of a cube on the grid.

    For the moment, only 2 entities have to appear on the grid: cubes and pipes.
    For that reason, we define cube positions (i.e., :class:`LayoutCubePosition2D`
    instances) to be on even coordinates and pipes positions to have one odd
    coordinates in the pipe dimension and even coordinates elsewhere.
    """

    def __init__(self, x: int, y: int) -> None:
        if (x % 2 == 1) or (y % 2 == 1):
            clsname = self.__class__.__name__
            raise TQECException(f"{clsname} cannot contain any odd coordinate.")
        super().__init__(x, y)

    @override
    def origin_qubit(
        self, element_shape: PhysicalQubitScalable2D, border_size: int
    ) -> PhysicalQubitScalable2D:
        x, y = self._x // 2, self._y // 2
        return PhysicalQubitScalable2D(x * element_shape.x, y * element_shape.y)

    def to_block_position(self) -> BlockPosition2D:
        return BlockPosition2D(self._x // 2, self._y // 2)


class LayoutPipePosition2D(LayoutPosition2D):
    """Internal class to represent the position of a cube on the grid.

    For the moment, only 2 entities have to appear on the grid: cubes and pipes.
    For that reason, we define cube positions (i.e., :class:`LayoutCubePosition2D`
    instances) to be on even coordinates and pipes positions to have one odd
    coordinates in the pipe dimension and even coordinates elsewhere.
    """

    def __init__(self, x: int, y: int) -> None:
        if not ((x % 2 == 1) ^ (y % 2 == 1)):
            clsname = self.__class__.__name__
            raise TQECException(
                f"{clsname} should contain one odd and one even coordinate."
            )
        super().__init__(x, y)

    @override
    def origin_qubit(
        self, element_shape: PhysicalQubitScalable2D, border_size: int
    ) -> PhysicalQubitScalable2D:
        x, y = int(ceil(self._x / 2)), int(ceil(self._y / 2))
        return PhysicalQubitScalable2D(
            x * element_shape.x - border_size * (self._x % 2),
            y * element_shape.y - border_size * (self._y % 2),
        )


T = TypeVar("T", bound=LayoutPosition2D, covariant=True, default=LayoutPosition2D)


class LayoutPosition3D(ABC, Generic[T]):
    """Internal class to represent the local indexing used to represent both
    cubes and pipes in 3-dimensions.

    This class simply wraps a :class:`LayoutPosition2D` instance with an
    integer-valued z coordinate.

    Because temporal pipes are "absorbed" in its neighbouring blocks, we do not
    have to represent them, hence the z coordinate does not need any kind of
    special treatment like the x and y coordinates.
    """

    def __init__(self, spatial_position: T, z: int) -> None:
        super().__init__()
        self._spatial_position = spatial_position
        self._z = z

    @staticmethod
    def from_block_position(
        pos: BlockPosition3D,
    ) -> LayoutPosition3D[LayoutCubePosition2D]:
        return LayoutPosition3D(
            LayoutCubePosition2D.from_block_position(pos.as_2d()), pos.z
        )

    @staticmethod
    def from_junction_position(
        junction_position: tuple[BlockPosition3D, BlockPosition3D],
    ) -> LayoutPosition3D[LayoutPipePosition2D]:
        u, v = sorted(junction_position)
        assert u.is_neighbour(v)
        assert u < v
        return LayoutPosition3D(
            LayoutPosition2D.from_junction_position((u.as_2d(), v.as_2d())), u.z
        )

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
