from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Generic, Iterable, Mapping, TypeVar

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

T = TypeVar("T", bound=BaseLayer)


@dataclass
class RepeatedLayer(BaseComposedLayer[T], Generic[T]):
    """Composed layer implementing repetition.

    This composed layer repeats another layer (that can be atomic or composed)
    multiple times.

    Attributes:
        internal_layer: repeated layer.
        repetitions: number of repetitions to perform. Can scale with ``k``.
    """

    internal_layer: T | BaseComposedLayer[T]
    repetitions: LinearFunction

    def __post_init__(self) -> None:
        # Check that the number of timesteps of self is a linear function.
        if (
            self.internal_layer.scalable_timesteps.slope != 0
            and self.repetitions.slope != 0
        ):
            raise TQECException(
                "Layers with a non-constant number of timesteps cannot be "
                "repeated a non-constant number of times as that would lead to "
                "a non-linear number of timesteps, which is not supported yet. "
                f"Got a layer with {self.internal_layer.scalable_timesteps} timesteps "
                f"and tried to repeat it {self.repetitions} times."
            )

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        if self.repetitions.slope == 0:
            return self.repetitions.offset * self.internal_layer.scalable_timesteps
        else:
            return self.repetitions * self.internal_layer.scalable_timesteps.offset

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.internal_layer.scalable_shape

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> RepeatedLayer[T]:
        return RepeatedLayer(
            self.internal_layer.with_spatial_borders_trimmed(borders), self.repetitions
        )

    @staticmethod
    def _get_replaced_layer(
        initial_layer: T | BaseComposedLayer[T],
        border: TemporalBlockBorder,
        border_replacements: Mapping[TemporalBlockBorder, T | None],
    ) -> T | BaseComposedLayer[T] | None:
        ret: T | BaseComposedLayer[T] | None = initial_layer
        if border in border_replacements:
            ret = initial_layer.with_temporal_borders_replaced(
                {border: border_replacements[border]}
            )
        return ret

    @override
    def with_temporal_borders_replaced(
        self,
        border_replacements: Mapping[TemporalBlockBorder, T | None],
    ) -> RepeatedLayer[T] | SequencedLayers[T]:
        # Does not handle "removing": the bulk_layers is never checked for
        # emptyness and so might be empty.
        if not border_replacements:
            return self
        initial_layer = self._get_replaced_layer(
            self.internal_layer, TemporalBlockBorder.Z_NEGATIVE, border_replacements
        )
        final_layer = self._get_replaced_layer(
            self.internal_layer, TemporalBlockBorder.Z_POSITIVE, border_replacements
        )

        num_borders = len(border_replacements)
        bulk_layers = RepeatedLayer(self.internal_layer, self.repetitions - num_borders)
        if initial_layer is None and final_layer is None:
            return bulk_layers
        layer_sequence = []
        if initial_layer is not None:
            layer_sequence.append(initial_layer)
        layer_sequence.append(bulk_layers)
        if final_layer is not None:
            layer_sequence.append(final_layer)
        return SequencedLayers(layer_sequence)

    @override
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        yield from chain.from_iterable(
            (
                (self.internal_layer,)
                if isinstance(self.internal_layer, BaseLayer)
                else self.internal_layer.all_layers(k)
            )
            for _ in range(self.repetitions.integer_eval(k))
        )
