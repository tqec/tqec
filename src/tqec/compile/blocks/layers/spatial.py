from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Final

from typing_extensions import Self

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.utils.position import PhysicalQubitShape2D
from tqec.utils.scale import PhysicalQubitScalable2D

EXPECTED_SPATIAL_BORDER_WIDTH: Final[int] = 2
"""Hard-coded expected spatial border width in qubit coordinates.

At the moment, we need to ensure that removing one spatial border from any given layer will trim out
a band of qubits with a known width. Some computations in the code base indirectly depends on the
fact that this value is 2 for historical reasons.

Even though we do not need to in the foreseeable future, changing that width will likely lead to
various errors in the code base.

"""


class WithSpatialFootprint(ABC):
    """Base class providing the interface implemented by objects that have a spatial footprint."""

    def __init__(self, trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset()):
        """Initialise the instance.

        Args:
            trimmed_spatial_borders: all the spatial borders that have been trimmed from the layer.

        """
        super().__init__()
        self._trimmed_spatial_borders = trimmed_spatial_borders

    @property
    @abstractmethod
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        """Return the 2-dimensional shape of the object.

        Note:
            This method should return the shape in qubit-coordinates. That means
            that usual plaquette for the rotated surface code measuring 4-body
            stabilizers (i.e., the square ones with a data-qubit on each corner
            and a syndrome qubit in the middle of the square) has a shape of
            ``(3, 3)``.

        Returns:
            the 2-dimensional shape **in qubit-coordinates** of the object as an
            exact expression that can then be used to compute the shape for any
            value of ``k``.

        """
        pass

    def shape(self, k: int) -> PhysicalQubitShape2D:
        """Return the 2-dimensional shape of the object for the given ``k``.

        Args:
            k: scaling parameter.

        Returns:
            the 2-dimensional shape of the object for the given ``k``.

        """
        return self.scalable_shape.to_shape_2d(k)  # pragma: no cover

    @abstractmethod
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> Self:
        """Return ``self`` with the provided spatial borders removed.

        Args:
            borders: spatial borders to remove.

        Returns:
            a copy of ``self`` with the provided ``borders`` removed.

        """
        pass

    @property
    def trimmed_spatial_borders(self) -> frozenset[SpatialBlockBorder]:
        """Get the spatial layers that have been trimmed off from ``self``."""
        return self._trimmed_spatial_borders
