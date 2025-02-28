from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Generic, Iterable, Mapping, Sequence, TypeVar

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
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
    def schedule(self) -> tuple[LinearFunction, ...]:
        """Returns the duration of each of the sequenced layers."""
        return tuple(layer.scalable_timesteps for layer in self.layer_sequence)

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

    def _layers_with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> list[T | BaseComposedLayer[T]]:
        return [
            layer.with_spatial_borders_trimmed(borders) for layer in self.layer_sequence
        ]

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> SequencedLayers[T]:
        return SequencedLayers(self._layers_with_spatial_borders_trimmed(borders))

    def _layers_with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, T | None]
    ) -> list[T | BaseComposedLayer[T]]:
        layers = list(self.layer_sequence)
        if (border := TemporalBlockBorder.Z_NEGATIVE) in border_replacements:
            first_layer = layers[0].with_temporal_borders_replaced(
                {border: border_replacements[border]}
            )
            if first_layer is not None:
                layers[0] = first_layer
            else:
                layers.pop(0)
        if not layers:
            return []
        if (border := TemporalBlockBorder.Z_POSITIVE) in border_replacements:
            last_layer = layers[-1].with_temporal_borders_replaced(
                {border: border_replacements[border]}
            )
            if last_layer is not None:
                layers[-1] = last_layer
            else:
                layers.pop(-1)
        return layers

    @override
    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, T | None]
    ) -> BaseComposedLayer[T] | None:
        if not border_replacements:
            return self
        layers = self._layers_with_temporal_borders_replaced(border_replacements)
        return SequencedLayers(layers) if layers else None

    @override
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        yield from chain.from_iterable(
            ((layer,) if isinstance(layer, BaseLayer) else layer.all_layers(k))
            for layer in self.layer_sequence
        )

    @override
    def to_sequenced_layer_with_schedule(
        self, schedule: tuple[LinearFunction, ...]
    ) -> SequencedLayers[T]:
        duration = sum(schedule, start=LinearFunction(0, 0))
        if self.scalable_timesteps != duration:
            raise TQECException(
                f"Cannot transform the {SequencedLayers.__name__} instance to a "
                f"{SequencedLayers.__name__} instance with the provided schedule. "
                f"The provided schedule has a duration of {duration} but the "
                f"instance to transform has a duration of {self.scalable_timesteps}."
            )
        if self.schedule == schedule:
            return self
        raise NotImplementedError(
            f"Adapting a {SequencedLayers.__name__} instance to another schedule "
            "is not yet implemented."
        )
