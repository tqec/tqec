from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.exceptions import TQECException
from tqec.scale import LinearFunction, Scalable2D


@dataclass
class SequencedLayers(BaseComposedLayer):
    layer_sequence: Sequence[BaseLayer]

    def __post_init__(self) -> None:
        shapes = frozenset(layer.scalable_shape for layer in self.layer_sequence)
        if len(shapes) == 0:
            raise TQECException(f"Cannot build an empty {self.__class__.__name__}")
        if len(shapes) > 1:
            raise TQECException(
                f"Found at least two different shapes in a {self.__class__.__name__}, "
                "which is forbidden. All the provided layers should have the same "
                f"shape. Found shapes: {shapes}."
            )

    @override
    def layers(self, k: int) -> Iterable[BaseLayer]:
        yield from self.layer_sequence

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return LinearFunction(0, len(self.layer_sequence))

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        # __post_init__ guarantees that there is at least one item in
        # self.layer_sequence and that all the layers have the same scalable shape.
        return self.layer_sequence[0].scalable_shape

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> SequencedLayers:
        return SequencedLayers(
            [
                layer.with_spatial_borders_trimed(borders)
                for layer in self.layer_sequence
            ]
        )

    @override
    def with_temporal_borders_trimed(self, borders: Iterable[TemporalBlockBorder]):
        layers: list[BaseLayer] = []
        if TemporalBlockBorder.Z_NEGATIVE in borders:
            first_layer = self.layer_sequence[0].with_temporal_borders_trimed(
                [TemporalBlockBorder.Z_NEGATIVE]
            )
            if first_layer is not None:
                layers.append(first_layer)
        layers.extend(self.layer_sequence[1:-1])
        if TemporalBlockBorder.Z_POSITIVE in borders:
            last_layer = self.layer_sequence[-1].with_temporal_borders_trimed(
                [TemporalBlockBorder.Z_POSITIVE]
            )
            if last_layer is not None:
                layers.append(last_layer)
        return SequencedLayers(layers)
