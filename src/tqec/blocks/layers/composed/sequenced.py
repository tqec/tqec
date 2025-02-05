from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Generic, Iterable, Sequence, TypeVar

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

T = TypeVar("T", bound=BaseLayer)


@dataclass
class SequencedLayers(BaseComposedLayer[T], Generic[T]):
    """Composed layer implementing a fixed sequence of layers.

    This composed layer sequentially applies layers from a fixed sequence.

    Attributes:
        layer_sequence: non-empty sequence of layers to apply one after the
            other. All the layers in this sequence should have exactly the same
            spatial footprint.
    """

    layer_sequence: Sequence[T | BaseComposedLayer[T]]

    def __post_init__(self) -> None:
        if len(self.layer_sequence) <= 1:
            clsname = SequencedLayers.__name__
            raise TQECException(
                f"An instance of {clsname} is expected to have multiple "
                f"layers in sequence. Found {len(self.layer_sequence)}."
            )
        shapes = frozenset(layer.scalable_shape for layer in self.layer_sequence)
        if len(shapes) == 0:
            raise TQECException(f"Cannot build an empty {self.__class__.__name__}")
        if len(shapes) > 1:
            raise TQECException(
                f"Found at least two different shapes in a {self.__class__.__name__}, "
                "which is forbidden. All the provided layers should have the same "
                f"shape. Found shapes: {shapes}."
            )

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return sum(
            (layer.scalable_timesteps for layer in self.layer_sequence),
            start=LinearFunction(0, 0),
        )

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
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
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> SequencedLayers | None:
        layers: list[T | BaseComposedLayer[T]] = []
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

    @override
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        yield from chain.from_iterable(
            ((layer,) if isinstance(layer, BaseLayer) else layer.all_layers(k))
            for layer in self.layer_sequence
        )
