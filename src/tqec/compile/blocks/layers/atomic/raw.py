from __future__ import annotations

from collections.abc import Callable, Iterable

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class RawCircuitLayer(BaseLayer):
    def __init__(
        self,
        circuit_factory: Callable[[int], ScheduledCircuit],
        scalable_raw_shape: PhysicalQubitScalable2D,
        scalable_num_moments: LinearFunction,
        trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset(),
    ):
        """Represent a layer with a spatial footprint that is defined by a raw circuit.

        Args:
            circuit_factory: a function callable returning a quantum circuit for
                any input ``k >= 1``.
            scalable_raw_shape: scalable shape of the quantum circuit returned
                by the provided ``circuit_factory``.
            scalable_num_moments: a linear function associating to any input
                ``k >= 1`` the number of moments returned by the provided
                ``circuit_factory`` when given ``k`` as input. This is expected
                to be constant in most scenario, but left as a linear function
                to cover potential edge-cases.
            trimmed_spatial_borders: all the spatial borders that have been
                removed from the layer.

        """
        super().__init__(trimmed_spatial_borders)
        self._circuit_factory = circuit_factory
        self._scalable_raw_shape = scalable_raw_shape
        self._scalable_num_moments = scalable_num_moments

    @property
    def scalable_raw_shape(self) -> PhysicalQubitScalable2D:
        """Get the scalable shape of the quantum circuit returned by ``self.circuit_factory``."""
        return self._scalable_raw_shape

    @property
    def circuit_factory(self) -> Callable[[int], ScheduledCircuit]:
        """Get the callable used to generate a scalable quantum circuit from the scaling factor."""
        return self._circuit_factory  # pragma: no cover

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

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    @property
    @override
    def scalable_num_moments(self) -> LinearFunction:
        return self._scalable_num_moments  # pragma: no cover
