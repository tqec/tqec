from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.spatial import WithSpatialFootprint
from tqec.compile.blocks.temporal import WithTemporalFootprint
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Shape2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@dataclass
class Block(WithSpatialFootprint, WithTemporalFootprint):
    """Encodes the implementation of a block.

    This data structure is voluntarilly very generic. It represents blocks as a
    sequence of layers that can be instances of either
    :class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` or
    :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`.

    Depending on the stored layers, this class can be used to represent regular
    cubes (i.e. scaling in the 2 spatial dimensions with ``k``) as well as
    pipes (i.e. scaling in only 1 spatial dimension with ``k``).

    Attributes:
        layers: a non-empty, time-ordered sequence of atomic or composed layers
            that all have the same spatial footprint.
    """

    layers: Sequence[BaseLayer | BaseComposedLayer[BaseLayer]]

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
    def scalable_shape(self) -> PhysicalQubitScalable2D:
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
    ) -> Block:
        return Block(
            [layer.with_spatial_borders_trimed(borders) for layer in self.layers]
        )

    def _add_layer_with_temporal_borders_trimed(
        self,
        layers: list[BaseLayer | BaseComposedLayer[BaseLayer]],
        layer_index: int,
        border: TemporalBlockBorder,
    ) -> None:
        layer = self.layers[layer_index].with_temporal_borders_trimed([border])
        if layer is not None:
            layers.append(layer)

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> Block:
        layers: list[BaseLayer | BaseComposedLayer[BaseLayer]] = []
        if TemporalBlockBorder.Z_NEGATIVE in borders:
            self._add_layer_with_temporal_borders_trimed(
                layers, 0, TemporalBlockBorder.Z_NEGATIVE
            )
        layers.extend(self.layers[1:-1])
        if TemporalBlockBorder.Z_POSITIVE in borders:
            self._add_layer_with_temporal_borders_trimed(
                layers, -1, TemporalBlockBorder.Z_POSITIVE
            )
        return Block(layers)

    def with_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder | TemporalBlockBorder]
    ) -> Block:
        spatial_borders: list[SpatialBlockBorder] = []
        temporal_borders: list[TemporalBlockBorder] = []
        for border in borders:
            if isinstance(border, SpatialBlockBorder):
                spatial_borders.append(border)
            else:
                temporal_borders.append(border)
        return self.with_temporal_borders_trimed(
            temporal_borders
        ).with_spatial_borders_trimed(spatial_borders)
