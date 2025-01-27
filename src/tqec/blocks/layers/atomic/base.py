from __future__ import annotations

from abc import abstractmethod
from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import TemporalBlockBorder
from tqec.blocks.spatial import WithSpatialFootprint
from tqec.blocks.temporal import WithTemporalFootprint
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.scale import LinearFunction


class BaseLayer(WithSpatialFootprint, WithTemporalFootprint):
    @abstractmethod
    def to_circuit(self, k: int) -> ScheduledCircuit:
        pass

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        return LinearFunction(0, 1)

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> None:
        return None
