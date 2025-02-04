from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.circuit.schedule.circuit import ScheduledCircuit
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
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> RawCircuitLayer:
        clsname = self.__class__.__name__
        raise NotImplementedError(
            f"Cannot trim spatial borders of a {clsname} instance."
        )
