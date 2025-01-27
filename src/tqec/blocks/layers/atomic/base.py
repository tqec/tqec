from __future__ import annotations

from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import TemporalBlockBorder
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint
from tqec.scale import LinearFunction


class BaseLayer(WithSpatialFootprint, WithTemporalFootprint):
    """Base class representing a "layer".

    A "layer" is defined as a quantum circuit implementing a single round of
    quantum error correction. It can span an arbitrarily large spatial area and
    implement a (time)slice of an arbitrarily complex quantum error corrected
    computation.
    """

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        # By definition of a "layer":
        return LinearFunction(0, 1)

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> BaseLayer | None:
        # Removing any temporal border from a layer means removing the whole
        # layer.
        trimed_borders = frozenset(borders)
        return None if trimed_borders else self
