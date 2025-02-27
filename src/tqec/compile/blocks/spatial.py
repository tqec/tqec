from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Final, Iterable

from typing_extensions import Self

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.utils.position import PhysicalQubitShape2D
from tqec.utils.scale import PhysicalQubitScalable2D

EXPECTED_SPATIAL_BORDER_WIDTH: Final[int] = 2
"""Hard-coded expected spatial border width in qubit coordinates.

At the moment, we need to ensure that removing one spatial border from any given
layer will trim out a band of qubits with a known width. Some computations in
the code base indirectly depends on the fact that this value is 2 for historical
reasons.

Even though we do not need to in the foreseeable future, changing that value
will likely lead to various errors in the code base.
"""


class WithSpatialFootprint(ABC):
    """Base class providing the interface that should be implemented by objects
    that have a spatial footprint."""

    @property
    @abstractmethod
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        """Returns the 2-dimensional shape of the object as an exact expression
        that can then be used to compute the shape for any value of ``k``.

        Returns:
            the 2-dimensional shape of the object as an exact expression
            that can then be used to compute the shape for any value of ``k``.
        """
        pass

    def shape(self, k: int) -> PhysicalQubitShape2D:
        """Returns the 2-dimensional shape of the object for the given ``k``.

        Args:
            k: scaling parameter.

        Returns:
            the 2-dimensional shape of the object for the given ``k``.
        """
        return self.scalable_shape.to_shape_2d(k)

    @abstractmethod
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> Self:
        """Returns ``self`` with the provided spatial borders removed.

        Args:
            borders: spatial borders to remove.

        Returns:
            a copy of ``self`` with the provided ``borders`` removed.
        """
        pass
