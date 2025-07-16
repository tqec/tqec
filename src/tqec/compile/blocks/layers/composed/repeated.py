from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import chain

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D, round_or_fail


class RepeatedLayer(BaseComposedLayer):
    def __init__(
        self,
        internal_layer: BaseLayer | BaseComposedLayer,
        repetitions: LinearFunction,
        trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset(),
    ):
        """Composed layer implementing repetition.

        This composed layer repeats another layer (that can be atomic or composed)
        multiple times.

        Args:
            internal_layer: repeated layer.
            repetitions: number of repetitions to perform. Can scale with ``k``.
            trimmed_spatial_borders: all the spatial borders that have been
                removed from the layer.

        Raises:
            TQECError: if the total number of timesteps is not a linear
                function (i.e., ``internal_layer.scalable_timesteps.slope != 0``
                and ``repetitions.slope != 0``).
            TQECError: if the total number of timesteps is strictly
                decreasing.

        """
        super().__init__(trimmed_spatial_borders)
        self._internal_layer = internal_layer
        self._repetitions = repetitions
        self._post_init_check()

    @property
    def internal_layer(self) -> BaseLayer | BaseComposedLayer:
        """Get the internal layer that is being repeated by ``self``."""
        return self._internal_layer

    @property
    def repetitions(self) -> LinearFunction:
        """Get the number of repetitions of the internal layer."""
        return self._repetitions

    def _post_init_check(self) -> None:
        # Check that the number of timesteps of self is a linear function.
        if self.internal_layer.scalable_timesteps.slope != 0 and self.repetitions.slope != 0:
            raise TQECError(
                "Layers with a non-constant number of timesteps cannot be "
                "repeated a non-constant number of times as that would lead to "
                "a non-linear number of timesteps, which is not supported yet. "
                f"Got a layer with {self.internal_layer.scalable_timesteps} timesteps "
                f"and tried to repeat it {self.repetitions} times."
            )
        # Check that the number of timesteps of ``self`` is not strictly decreasing.
        if self.repetitions.slope < 0 or self.internal_layer.scalable_timesteps.slope < 0:
            raise TQECError(
                f"Cannot create a {RepeatedLayer.__name__} instance with a decreasing "
                f"number of timesteps. Got repeated layer with "
                f"{self.internal_layer.scalable_timesteps} timesteps that is repeated "
                f"{self.repetitions} times, that would lead to a total duration of "
                f"{self.scalable_timesteps}, which is strictly decreasing."
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
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> RepeatedLayer:
        return RepeatedLayer(
            self.internal_layer.with_spatial_borders_trimmed(borders),
            self.repetitions,
            self.trimmed_spatial_borders | frozenset(borders),
        )

    @staticmethod
    def _get_replaced_layer(
        initial_layer: BaseLayer | BaseComposedLayer,
        border: TemporalBlockBorder,
        border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None],
    ) -> BaseLayer | BaseComposedLayer | None:
        ret: BaseLayer | BaseComposedLayer | None = initial_layer
        if border in border_replacements:
            ret = initial_layer.with_temporal_borders_replaced(
                {border: border_replacements[border]}
            )
        return ret

    @override
    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | BaseComposedLayer | None:
        if not border_replacements:
            return self
        # Compute the bulk layer
        num_borders = len(border_replacements)
        bulk_repetitions = self.repetitions - num_borders
        bulk_layer: BaseLayer | BaseComposedLayer | None
        if bulk_repetitions == LinearFunction(0, 0):
            bulk_layer = None
        elif bulk_repetitions == LinearFunction(0, 1):
            bulk_layer = self.internal_layer
        else:
            bulk_layer = RepeatedLayer(self.internal_layer, bulk_repetitions)

        # Compute the layers at each temporal sides
        initial_layer = self._get_replaced_layer(
            self.internal_layer, TemporalBlockBorder.Z_NEGATIVE, border_replacements
        )
        final_layer = self._get_replaced_layer(
            self.internal_layer, TemporalBlockBorder.Z_POSITIVE, border_replacements
        )
        # Build the resulting layer sequence
        layer_sequence = []
        if (
            # the initial layer has not been removed by the replacement
            initial_layer is not None
            # and it was replaced (i.e., not already accounted for in bulk_layer)
            and TemporalBlockBorder.Z_NEGATIVE in border_replacements
        ):
            layer_sequence.append(initial_layer)
        if bulk_layer is not None:
            layer_sequence.append(bulk_layer)
        if (
            # the final layer has not been removed by the replacement
            final_layer is not None
            # and it was replaced (i.e., not already accounted for in bulk_layer)
            and TemporalBlockBorder.Z_POSITIVE in border_replacements
        ):
            layer_sequence.append(final_layer)
        match len(layer_sequence):
            case 0:
                return None
            case 1:
                return layer_sequence[0]
            case _:
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

    @override
    def to_sequenced_layer_with_schedule(
        self, schedule: tuple[LinearFunction, ...]
    ) -> SequencedLayers:
        duration = sum(schedule, start=LinearFunction(0, 0))
        if self.scalable_timesteps != duration:
            raise TQECError(
                f"Cannot transform the {RepeatedLayer.__name__} instance to a "
                f"{SequencedLayers.__name__} instance with the provided schedule. "
                f"The provided schedule has a duration of {duration} but the "
                f"instance to transform has a duration of {self.scalable_timesteps}."
            )
        body_duration_scalable = self.internal_layer.scalable_timesteps
        if not body_duration_scalable.is_constant():
            raise NotImplementedError(
                f"Splitting a {RepeatedLayer.__name__} instance with a "
                "non-constant duration body is not implemented yet."
            )
        body_duration = round_or_fail(body_duration_scalable.offset)
        layers: list[BaseLayer | BaseComposedLayer] = []
        for s in schedule:
            try:
                repetitions = s.exact_integer_div(body_duration)
            except TQECError as e:
                raise NotImplementedError(
                    f"The ability to split the body of a {RepeatedLayer.__name__} "
                    "instance has not been implemented yet. Trying to fit an "
                    f"integer repetition of a body with a duration of {body_duration} "
                    f"within a total duration of {s}."
                ) from e
            layers.append(
                RepeatedLayer(self.internal_layer, repetitions)
                if repetitions != LinearFunction(0, 1)
                else self.internal_layer
            )
        return SequencedLayers(layers)

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, RepeatedLayer)
            and self.repetitions == value.repetitions
            and self.internal_layer == value.internal_layer
        )

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    @override
    def get_temporal_layer_on_border(self, border: TemporalBlockBorder) -> BaseLayer:
        return self.internal_layer.get_temporal_layer_on_border(border)

    @property
    @override
    def scalable_num_moments(self) -> LinearFunction:
        return LinearFunction.safe_mul(self.internal_layer.scalable_num_moments, self.repetitions)
