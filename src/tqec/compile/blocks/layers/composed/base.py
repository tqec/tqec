from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Iterable, Mapping

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.spatial import WithSpatialFootprint
from tqec.compile.blocks.layers.temporal import WithTemporalFootprint
from tqec.utils.scale import LinearFunction

if TYPE_CHECKING:
    from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers


class BaseComposedLayer(WithSpatialFootprint, WithTemporalFootprint):
    """Base class representing a composed "layer".

    A composed layer is defined as a sequence (in time) of atomic layers. As
    such, composed layers are expected to have either a scalable time footprint
    (i.e., that grows with ``k``) or a constant time footprint that is strictly
    greater than ``1``.
    """

    @abstractmethod
    def all_layers(self, k: int) -> Iterable[BaseLayer]:
        """Returns all the base layers represented by the instance.

        Returns:
            All the base layers represented by the instance. The returned
            iterable should have as many entries as ``self.timesteps(k)``.
        """
        pass

    @abstractmethod
    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | BaseComposedLayer | None:
        """Returns ``self`` with the provided temporal borders replaced.

        Args:
            borders: a mapping from temporal borders to replace to their
                replacement. A value of ``None`` as a replacement means that the
                border is removed.

        Returns:
            a copy of ``self`` with the provided ``borders`` replaced, or ``None``
            if replacing the provided ``borders`` from ``self`` result in an
            empty temporal footprint.
        """
        pass

    @abstractmethod
    def to_sequenced_layer_with_schedule(
        self, schedule: tuple[LinearFunction, ...]
    ) -> SequencedLayers:
        """Splits ``self`` into a :class:`~tqec.compile.blocks.layers.composed.sequenced.SequencedLayers`
        instance with the provided schedule.

        Args:
            schedule: duration of each of the layers in the returned
                :class:`~tqec.compile.blocks.layers.composed.sequenced.SequencedLayers`
                instance.

        Returns:
            an instance of :class:`~tqec.compile.blocks.layers.composed.sequenced.SequencedLayers`
            that is equivalent to ``self`` (same duration, same layers applied,
            ...) and that has the provided ``schedule``.
        """
        pass
