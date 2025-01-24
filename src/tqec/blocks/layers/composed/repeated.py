from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.scale import LinearFunction, Scalable2D
from tqec.templates.indices.enums import TemplateBorder


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
    def with_borders_trimed(self, borders: Iterable[TemplateBorder]) -> RepeatedLayer:
        return RepeatedLayer(self.layer.with_borders_trimed(borders), self.repetitions)
