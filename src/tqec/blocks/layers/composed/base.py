from __future__ import annotations

from abc import abstractmethod
from typing import Iterable

from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint
from tqec.templates.indices.enums import TemplateBorder


class BaseComposedLayer(WithSpatialFootprint, WithTemporalFootprint):
    @abstractmethod
    def layers(self, k: int) -> Iterable[BaseLayer]:
        pass

    @abstractmethod
    def with_borders_trimed(
        self, borders: Iterable[TemplateBorder]
    ) -> BaseComposedLayer:
        pass
