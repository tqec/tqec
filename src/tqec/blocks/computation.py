from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.blocks.layers.composed.base import BaseComposedLayer, BaseLayer
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint
from tqec.exceptions import TQECException
from tqec.position import Shape2D
from tqec.scale import LinearFunction, Scalable2D


@dataclass
class ComputationBlock(WithSpatialFootprint, WithTemporalFootprint):
    """Encodes the implementation of a block performing some kind of computation.

    This data structure is voluntarilly very generic. It represents blocks as a
    sequence of layers that can be instances of either
    :class:`~tqec.blocks.layers.atomic.base.BaseLayer` or
    :class:`~tqec.blocks.layers.composed.base.BaseComposedLayer`.

    Attributes:
        layers: a non-empty, time-ordered sequence of atomic or composed layers
            that all have the same spatial footprint.
    """

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

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> ComputationBlock:
        return ComputationBlock(
            [layer.with_spatial_borders_trimed(borders) for layer in self.layers]
        )

    def _add_layer_with_temporal_borders_trimed(
        self,
        layers: list[BaseLayer | BaseComposedLayer],
        layer_index: int,
        border: TemporalBlockBorder,
    ) -> None:
        layer = self.layers[layer_index].with_temporal_borders_trimed([border])
        if layer is not None:
            layers.append(layer)

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> ComputationBlock:
        layers: list[BaseLayer | BaseComposedLayer] = []
        if TemporalBlockBorder.Z_NEGATIVE in borders:
            self._add_layer_with_temporal_borders_trimed(
                layers, 0, TemporalBlockBorder.Z_NEGATIVE
            )
        layers.extend(self.layers[1:-1])
        if TemporalBlockBorder.Z_POSITIVE in borders:
            self._add_layer_with_temporal_borders_trimed(
                layers, -1, TemporalBlockBorder.Z_POSITIVE
            )
        return ComputationBlock(layers)

    @staticmethod
    def _split_borders(
        borders: Iterable[SpatialBlockBorder | TemporalBlockBorder],
    ) -> tuple[frozenset[SpatialBlockBorder], frozenset[TemporalBlockBorder]]:
        spatial_borders: list[SpatialBlockBorder] = []
        temporal_borders: list[TemporalBlockBorder] = []
        for border in borders:
            if isinstance(border, SpatialBlockBorder):
                spatial_borders.append(border)
            else:
                temporal_borders.append(border)
        return frozenset(spatial_borders), frozenset(temporal_borders)
