from __future__ import annotations

from collections.abc import Mapping

from typing_extensions import override

from tqec.compile.blocks.enums import TemporalBlockBorder
from tqec.compile.blocks.layers.spatial import WithSpatialFootprint
from tqec.compile.blocks.layers.temporal import WithTemporalFootprint
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction


class BaseLayer(WithSpatialFootprint, WithTemporalFootprint):
    """Base class representing a "layer".

    A "layer" is a scalable and repeatable unit of a quantum error correction
    circuit. In most cases, it corresponds to a single round of the syndrome
    extraction circuit. A base layer occupies a specific spacetime footprint,
    where the spatial footprint scales with the layer circuit, while the temporal
    footprint remains fixed at ``1``, representing a single layer. To stack layers
    over time or repeat them in a scalable manner, use
    :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer` instead.

    """

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        # By definition of a "layer":
        return LinearFunction(0, 1)

    @override
    def with_temporal_borders_replaced(
        self, border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None]
    ) -> BaseLayer | None:
        if not border_replacements:
            return self
        if len(border_replacements) > 1 and any(
            replacement is not None for replacement in border_replacements.values()
        ):
            raise TQECError(
                "Unclear semantic: trying to replace the two temporal borders of "
                "an atomic layer that, by definition, only contain one layer."
            )
        return next(iter(border_replacements.values()))

    @override
    def get_temporal_layer_on_border(self, border: TemporalBlockBorder) -> BaseLayer:
        return self
