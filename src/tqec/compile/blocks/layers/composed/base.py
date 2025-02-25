from __future__ import annotations

from abc import abstractmethod
from typing import Generic, Iterable, Mapping, TypeVar

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.spatial import WithSpatialFootprint
from tqec.compile.blocks.temporal import WithTemporalFootprint

T = TypeVar("T", bound=BaseLayer)


class BaseComposedLayer(WithSpatialFootprint, WithTemporalFootprint, Generic[T]):
    """Base class representing a composed "layer".

    A composed layer is defined as a sequence (in time) of atomic layers. As
    such, composed layers are expected to have either a scalable time footprint
    (i.e., that grows with ``k``) or a constant time footprint that is strictly
    greater than ``1``.
    """

    @abstractmethod
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        pass

    def with_temporal_borders_trimmed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> BaseComposedLayer[T] | None:
        """Returns ``self`` with the provided temporal borders removed.

        Args:
            borders: temporal borders to remove.

        Returns:
            a copy of ``self`` with the provided ``borders`` removed, or ``None``
            if removing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.
        """
        return self.with_temporal_borders_replaced({border: None for border in borders})

    @abstractmethod
    def with_temporal_borders_replaced(
        self,
        border_replacements: Mapping[TemporalBlockBorder, T | None],
    ) -> BaseComposedLayer[T] | None:
        """Returns ``self`` with the provided temporal borders replaced.

        Args:
            borders: a mapping from temporal borders to replace to their
                replacement. A value of ``None`` as a replacement means that the
                border is removed.

        Returns:
            a copy of ``self`` with the provided ``borders`` replaced, or ``None``
            if replacing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.
        """
        pass
