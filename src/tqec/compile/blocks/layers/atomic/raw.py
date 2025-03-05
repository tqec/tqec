from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.utils.scale import PhysicalQubitScalable2D


@dataclass
class RawCircuitLayer(BaseLayer):
    """Represents a layer with a spatial footprint that is defined by a raw
    circuit."""

    circuit_factory: Callable[[int], ScheduledCircuit]
    scalable_raw_shape: PhysicalQubitScalable2D

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.scalable_raw_shape

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> RawCircuitLayer:
        raise NotImplementedError(
            f"Cannot trim spatial borders of a {RawCircuitLayer.__name__} instance."
        )

    @override
    def __eq__(self, value: object) -> bool:
        raise NotImplementedError()
