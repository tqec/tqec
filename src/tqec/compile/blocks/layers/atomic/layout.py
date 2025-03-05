from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import PhysicalQubitScalable2D

DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER: Final[int] = 1
"""Default number of qubits that are shared between two neighbouring layers."""


@dataclass(frozen=True)
class LayoutLayer(BaseLayer):
    """A layer gluing several other layers together on a 2-dimensional grid."""

    layers: dict[LayoutPosition2D, BaseLayer]
    element_shape: PhysicalQubitScalable2D

    def __post_init__(self) -> None:
        if not self.layers:
            clsname = self.__class__.__name__
            raise TQECException(
                f"An instance of {clsname} should have at least one layer."
            )

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        xs = [pos._x for pos in self.layers.keys()]
        ys = [pos._y for pos in self.layers.keys()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        shapex, shapey = (maxx - minx) // 2 + 1, (maxy - miny) // 2 + 1
        return PhysicalQubitScalable2D(
            shapex * (self.element_shape.x - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
            shapey * (self.element_shape.y - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
        )

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> LayoutLayer:
        clsname = self.__class__.__name__
        raise TQECException(f"Cannot trim spatial borders of a {clsname} instance.")

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, LayoutLayer)
            and self.element_shape == value.element_shape
            and self.layers == value.layers
        )
