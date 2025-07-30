from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from itertools import chain

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class SequencedLayers(BaseComposedLayer):
    def __init__(
        self,
        layer_sequence: Sequence[BaseLayer | BaseComposedLayer],
        trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset(),
    ):
        """Composed layer implementing a fixed sequence of layers.

        This composed layer sequentially applies layers from a fixed sequence.

        Args:
            layer_sequence: non-empty sequence of layers to apply one after the
                other. All the layers in this sequence should have exactly the same
                spatial footprint.
            trimmed_spatial_borders: all the spatial borders that have been
                removed from the layer.

        Raises:
            TQECError: if the provided ``layer_sequence`` is empty.

        """
        super().__init__(trimmed_spatial_borders)
        self._layer_sequence = layer_sequence
        self._post_init_check()

    @property
    def layer_sequence(self) -> Sequence[BaseLayer | BaseComposedLayer]:
        """Get the sequence of layers stored by ``self``."""
        return self._layer_sequence

    def _post_init_check(self) -> None:
        if len(self.layer_sequence) < 1:
            raise TQECError(
                f"An instance of {type(self).__name__} is expected to have "
                f"at least one layer. Found {len(self.layer_sequence)}."
            )

    @property
    def schedule(self) -> tuple[LinearFunction, ...]:
        """Return the duration of each of the sequenced layers."""
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
        if any(isinstance(layer, LayoutLayer) for layer in self._layer_sequence):
            raise NotImplementedError(
                f"Computation of the scalable_shape for {LayoutLayer.__name__} "
                "instances has not been implemented yet."
            )
        scalable_shape = self._layer_sequence[0].scalable_shape
        for layer in self._layer_sequence[1:]:
            if layer.scalable_shape != scalable_shape:
                raise TQECError("Found a different scalable shape.")
        return scalable_shape

    def _layers_with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> list[BaseLayer | BaseComposedLayer]:
        return [layer.with_spatial_borders_trimmed(borders) for layer in self.layer_sequence]

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> SequencedLayers:
        return SequencedLayers(
            self._layers_with_spatial_borders_trimmed(borders),
            self.trimmed_spatial_borders | frozenset(borders),
        )

    def _layers_with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> list[BaseLayer | BaseComposedLayer]:
        layers = list(self.layer_sequence)
        if (border := TemporalBlockBorder.Z_NEGATIVE) in border_replacements:
            first_layer = layers[0].with_temporal_borders_replaced(
                {border: border_replacements[border]}
            )
            if first_layer is not None:
                layers[0] = first_layer
            else:
                layers.pop(0)
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
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | BaseComposedLayer | None:
        if not border_replacements:
            return self
        layers = self._layers_with_temporal_borders_replaced(border_replacements)
        match len(layers):
            case 0:
                return None
            case 1:
                return layers[0]
            case _:
                return SequencedLayers(layers)

    @override
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        yield from chain.from_iterable(
            ((layer,) if isinstance(layer, BaseLayer) else layer.all_layers(k))
            for layer in self.layer_sequence
        )

    @override
    def to_sequenced_layer_with_schedule(
        self, schedule: tuple[LinearFunction, ...]
    ) -> SequencedLayers:
        duration = sum(schedule, start=LinearFunction(0, 0))
        if self.scalable_timesteps != duration:
            raise TQECError(
                f"Cannot transform the {SequencedLayers.__name__} instance to a "
                f"{SequencedLayers.__name__} instance with the provided schedule. "
                f"The provided schedule has a duration of {duration} but the "
                f"instance to transform has a duration of {self.scalable_timesteps}."
            )
        if self.schedule == schedule:
            return self
        raise NotImplementedError(
            f"Adapting a {SequencedLayers.__name__} instance to another "
            "schedule is not yet implemented."
        )

    def __eq__(self, value: object) -> bool:
        return isinstance(value, SequencedLayers) and self.layer_sequence == value.layer_sequence

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    @override
    def get_temporal_layer_on_border(self, border: TemporalBlockBorder) -> BaseLayer:
        return self._layer_sequence[
            0 if border == TemporalBlockBorder.Z_NEGATIVE else -1
        ].get_temporal_layer_on_border(border)

    @property
    @override
    def scalable_num_moments(self) -> LinearFunction:
        return sum(
            (layer.scalable_num_moments for layer in self.layer_sequence),
            start=LinearFunction(0, 0),
        )
