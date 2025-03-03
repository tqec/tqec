from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction


@dataclass
class Block(SequencedLayers[BaseLayer]):
    """Encodes the implementation of a block.

    This data structure is voluntarily very generic. It represents blocks as a
    sequence of layers that can be instances of either
    :class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` or
    :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`.

    Depending on the stored layers, this class can be used to represent regular
    cubes (i.e. scaling in the 3 dimensions with ``k``) as well as pipes (i.e.
    scaling in only 2 dimension with ``k``).
    """

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> Block:
        return Block(self._layers_with_spatial_borders_trimmed(borders))

    @override
    def with_temporal_borders_replaced(
        self,
        border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None],
    ) -> Block | None:
        if not border_replacements:
            return self
        layers = self._layers_with_temporal_borders_replaced(border_replacements)
        return Block(layers) if layers else None

    def get_temporal_border(self, border: TemporalBlockBorder) -> BaseLayer:
        layer_index: int
        match border:
            case TemporalBlockBorder.Z_NEGATIVE:
                layer_index = 0
            case TemporalBlockBorder.Z_POSITIVE:
                layer_index = -1
        layer = self.layer_sequence[layer_index]
        if not isinstance(layer, BaseLayer):
            raise TQECException(
                "Expected to recover a temporal **border** (i.e. an atomic "
                f"layer) but got an instance of {type(layer).__name__} instead."
            )
        return layer

    @property
    def dimensions(self) -> tuple[LinearFunction, LinearFunction, LinearFunction]:
        """Returns the dimensions of ``self``.

        Returns:
            a 3-dimensional tuple containing the width for each of the
            ``(x, y, z)`` dimensions.
        """
        spatial_shape = self.scalable_shape
        return spatial_shape.x, spatial_shape.y, self.scalable_timesteps

    @property
    def is_cube(self) -> bool:
        return all(dim.is_scalable() for dim in self.dimensions)

    @property
    def is_pipe(self) -> bool:
        return sum(dim.is_scalable() for dim in self.dimensions) == 2

    @property
    def is_temporal_pipe(self) -> bool:
        return self.is_pipe and self.dimensions[2].is_constant()
