from __future__ import annotations

from abc import ABC, abstractmethod
from math import ceil

from typing_extensions import override

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

    def __hash__(self):
        return hash((self._x, self._y))


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


class LayoutPosition3D(ABC):
    """Internal class to represent the local indexing used to represent both
    cubes and pipes in 3-dimensions."""

    def __init__(self, x: int, y: int, z: int) -> None:
        super().__init__()
        self._x = x
        self._y = y
        self._z = z

    @staticmethod
    def from_block_position(pos: BlockPosition3D) -> LayoutCubePosition3D:
        return LayoutCubePosition3D(2 * pos.x, 2 * pos.y, 2 * pos.z)

    @staticmethod
    def from_junction_position(
        junction_position: tuple[BlockPosition3D, BlockPosition3D],
    ) -> LayoutPipePosition3D:
        u, v = sorted(junction_position)
        assert u.is_neighbour(v)
        assert u < v
        return LayoutPipePosition3D(
            2 * u.x + (u.x != v.x), 2 * u.y + (u.y != v.y), 2 * u.z + (u.z != v.z)
        )

    def __hash__(self):
        return hash((self._x, self._y))

    @abstractmethod
    def as_2d(self) -> LayoutPosition2D:
        pass

    @property
    def is_temporal_pipe(self) -> bool:
        return self._z % 2 == 1

    @property
    def is_spatial_pipe(self) -> bool:
        return self._x % 2 == 1 or self._y % 2 == 1

    @property
    def is_pipe(self) -> bool:
        return self.is_spatial_pipe or self.is_temporal_pipe

    @property
    def is_cube(self) -> bool:
        return not self.is_pipe

    @property
    def z_ordering(self) -> int:
        return self._z


class LayoutCubePosition3D(LayoutPosition3D):
    """Internal class to represent the position of a cube on the grid.

    For the moment, only 2 entities have to appear on the grid: cubes and pipes.
    For that reason, we define cube positions (i.e., :class:`LayoutCubePosition3D`
    instances) to be on even coordinates and pipes positions to have one odd
    coordinates in the pipe dimension and even coordinates elsewhere.
    """

    def __init__(self, x: int, y: int, z: int) -> None:
        if (x % 2 == 1) or (y % 2 == 1) or (z % 2 == 1):
            clsname = self.__class__.__name__
            raise TQECException(f"{clsname} cannot contain any odd coordinate.")
        super().__init__(x, y, z)

    @override
    def as_2d(self) -> LayoutCubePosition2D:
        return LayoutCubePosition2D(self._x, self._y)


class LayoutPipePosition3D(LayoutPosition3D):
    """Internal class to represent the position of a cube on the grid.

    For the moment, only 2 entities have to appear on the grid: cubes and pipes.
    For that reason, we define cube positions (i.e., :class:`LayoutCubePosition2D`
    instances) to be on even coordinates and pipes positions to have one odd
    coordinates in the pipe dimension and even coordinates elsewhere.
    """

    def __init__(self, x: int, y: int, z: int) -> None:
        if sum(coord % 2 for coord in (x, y, z)) != 1:
            clsname = self.__class__.__name__
            raise TQECException(f"{clsname} should contain exactly one odd coordinate.")
        super().__init__(x, y, z)

    @override
    def as_2d(self) -> LayoutPipePosition2D | LayoutCubePosition2D:
        if self.is_temporal_pipe:
            return LayoutCubePosition2D(self._x, self._y)
        return LayoutPipePosition2D(self._x, self._y)
