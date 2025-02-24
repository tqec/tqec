from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Iterable

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition2D
from tqec.utils.scale import PhysicalQubitScalable2D


@dataclass(frozen=True)
class LayoutLayer(BaseLayer):
    """A layer gluing several other layers together on a 2-dimensional grid."""

    layers: dict[BlockPosition2D, BaseLayer]

    def __post_init__(self) -> None:
        if not self.layers:
            clsname = self.__class__.__name__
            raise TQECException(
                f"An instance of {clsname} should have at least one layer."
            )
        scalable_shapes = frozenset(
            layer.scalable_shape for layer in self.layers.values()
        )
        if len(scalable_shapes) > 1:
            raise TQECException(
                "Found different scalable shapes in the provided layers: "
                f"{scalable_shapes}. This is not permitted."
            )

    @cached_property
    def block_origin(self) -> BlockPosition2D:
        positions = list(self.layers.keys())
        xs, ys = [p.x for p in positions], [p.y for p in positions]
        return BlockPosition2D(min(xs), min(ys))

    @cached_property
    def _block_width(self) -> BlockPosition2D:
        positions = list(self.layers.keys())
        xs, ys = [p.x for p in positions], [p.y for p in positions]
        return BlockPosition2D(max(xs) - min(xs), max(ys) - min(ys))

    @cached_property
    def element_shape(self) -> PhysicalQubitScalable2D:
        return next(iter(self.layers.values())).scalable_shape

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        block_width = self._block_width
        element_shape = self.element_shape
        return PhysicalQubitScalable2D(
            block_width.x * element_shape.x, block_width.y * element_shape.y
        )

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> LayoutLayer:
        clsname = self.__class__.__name__
        raise TQECException(f"Cannot trim spatial borders of a {clsname} instance.")
