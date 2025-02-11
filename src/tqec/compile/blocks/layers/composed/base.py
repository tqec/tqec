from __future__ import annotations

from abc import abstractmethod
from typing import Generic, Iterable, TypeVar

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
