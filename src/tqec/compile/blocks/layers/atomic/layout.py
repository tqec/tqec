from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Iterable

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.positioning import (
    LayoutCubePosition2D,
    LayoutPipePosition2D,
    LayoutPosition2D,
)
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import PhysicalQubitScalable2D


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

    @cached_property
    def cube_positions(self) -> list[LayoutCubePosition2D]:
        return [
            pos for pos in self.layers.keys() if isinstance(pos, LayoutCubePosition2D)
        ]

    @cached_property
    def pipe_positions(self) -> list[LayoutPipePosition2D]:
        return [
            pos for pos in self.layers.keys() if isinstance(pos, LayoutPipePosition2D)
        ]

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.element_shape

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> LayoutLayer:
        clsname = self.__class__.__name__
        raise TQECException(f"Cannot trim spatial borders of a {clsname} instance.")
