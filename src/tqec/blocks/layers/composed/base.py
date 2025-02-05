from __future__ import annotations

from typing import Generic, TypeVar

from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint

T = TypeVar("T", bound=BaseLayer)


class BaseComposedLayer(WithSpatialFootprint, WithTemporalFootprint, Generic[T]):
    """Base class representing a composed "layer".

    A composed layer is defined as a sequence (in time) of atomic layers. As
    such, composed layers are expected to have either a scalable time footprint
    (i.e., that grows with ``k``) or a constant time footprint that is stricly
    greater than ``1``.
    """

    # @abstractmethod
    # def layers(self, k: int) -> Iterable[BaseLayer]:
    #     pass
