from __future__ import annotations

from typing import Callable, Iterable

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.utils.scale import PhysicalQubitScalable2D


class RawCircuitLayer(BaseLayer):
    def __init__(
        self,
        circuit_factory: Callable[[int], ScheduledCircuit],
        scalable_raw_shape: PhysicalQubitScalable2D,
        trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset(),
    ):
        """Represents a layer with a spatial footprint that is defined by a raw
        circuit.

        Args:
            circuit_factory: a function callable returning a quantum circuit for
                any input ``k >= 1``.
            scalable_raw_shape: scalable shape of the quantum circuit returned
                by the provided ``circuit_factory``.
            trimmed_spatial_borders: all the spatial borders that have been
                removed from the layer.

        """
        super().__init__(trimmed_spatial_borders)
        self._circuit_factory = circuit_factory
        self._scalable_raw_shape = scalable_raw_shape

    @property
    def scalable_raw_shape(self) -> PhysicalQubitScalable2D:
        return self._scalable_raw_shape

    @property
    def circuit_factory(self) -> Callable[[int], ScheduledCircuit]:
        return self._circuit_factory

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
