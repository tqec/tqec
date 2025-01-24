from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from typing_extensions import override

from tqec.blocks.layers.composed.base import BaseComposedLayer, BaseLayer
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint
from tqec.exceptions import TQECException
from tqec.position import Shape2D
from tqec.scale import LinearFunction, Scalable2D
from tqec.templates.indices.enums import TemplateBorder


@dataclass
class ComputationBlock(WithSpatialFootprint, WithTemporalFootprint):
    layers: Sequence[BaseLayer | BaseComposedLayer]

    def __post_init__(self) -> None:
        shapes = frozenset(layer.scalable_shape for layer in self.layers)
        if len(shapes) == 0:
            raise TQECException(f"Cannot build an empty {self.__class__.__name__}")
        if len(shapes) > 1:
            raise TQECException(
                "Found at least two different shapes in the layers of a "
                f"{self.__class__.__name__}, which is forbidden. All the "
                f"provided layers should have the same shape. "
                f"Found shapes: {shapes}."
            )

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        # __post_init__ guarantees that there is at least one item in
        # self.layer_sequence and that all the layers have the same scalable shape.
        return self.layers[0].scalable_shape

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return sum(
            (layer.scalable_timesteps for layer in self.layers),
            start=LinearFunction(0, 0),
        )

    @override
    def shape(self, k: int) -> Shape2D:
        return self.scalable_shape.to_shape_2d(k)

    def with_borders_trimed(
        self, borders: Iterable[TemplateBorder]
    ) -> ComputationBlock:
        return ComputationBlock(
            [layer.with_borders_trimed(borders) for layer in self.layers]
        )
