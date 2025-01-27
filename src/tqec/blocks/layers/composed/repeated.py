from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.scale import LinearFunction, Scalable2D


@dataclass
class RepeatedLayer(BaseComposedLayer):
    layer: BaseLayer
    repetitions: LinearFunction

    @override
    def layers(self, k: int) -> Iterable[BaseLayer]:
        yield from (self.layer for _ in range(self.timesteps(k)))

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return self.repetitions

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        return self.layer.scalable_shape

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> RepeatedLayer:
        return RepeatedLayer(
            self.layer.with_spatial_borders_trimed(borders), self.repetitions
        )

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> RepeatedLayer | None:
        return RepeatedLayer(self.layer, self.repetitions - len(frozenset(borders)))
