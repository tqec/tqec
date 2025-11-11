from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final, cast

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.layers.merge import (
    contains_only_base_layers,
    contains_only_composed_layers,
    merge_base_layers,
    merge_composed_layers,
)
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


class Block(SequencedLayers):
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
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> Block:
        return Block(
            self._layers_with_spatial_borders_trimmed(borders),
            self.trimmed_spatial_borders | frozenset(borders),
        )

    @override
    def with_temporal_borders_replaced(
        self,
        border_replacements: Mapping[TemporalBlockBorder, BaseLayer | None],
    ) -> Block | None:
        if not border_replacements:
            return self
        layers = self._layers_with_temporal_borders_replaced(border_replacements)
        return Block(layers) if layers else None

    def get_atomic_temporal_border(self, border: TemporalBlockBorder) -> BaseLayer:
        """Get the layer at the provided temporal ``border``.

        This method is different to :meth:`get_temporal_layer_on_border` in that it raises when the
        border is not an atomic layer.

        Raises:
            TQECError: if the layer at the provided temporal ``border`` is not atomic (i.e., an
                instance of :class:`.BaseLayer`).

        """
        layer_index: int
        match border:
            case TemporalBlockBorder.Z_NEGATIVE:
                layer_index = 0
            case TemporalBlockBorder.Z_POSITIVE:
                layer_index = -1
        layer = self.layer_sequence[layer_index]
        if not isinstance(layer, BaseLayer):
            raise TQECError(
                "Expected to recover a temporal **border** (i.e. an atomic "
                f"layer) but got an instance of {type(layer).__name__} instead."
            )
        return layer

    @property
    def dimensions(self) -> tuple[LinearFunction, LinearFunction, LinearFunction]:
        """Return the dimensions of ``self``.

        Returns:
            a 3-dimensional tuple containing the width for each of the
            ``(x, y, z)`` dimensions.

        """
        spatial_shape = self.scalable_shape
        return spatial_shape.x, spatial_shape.y, self.scalable_timesteps

    @property
    def is_cube(self) -> bool:
        """Return ``True`` if ``self`` represents a cube, else ``False``.

        A cube is defined as a block with all its 3 dimensions that are scalable.

        """
        return all(dim.is_scalable() for dim in self.dimensions)

    @property
    def is_pipe(self) -> bool:
        """Return ``True`` if ``self`` represents a pipe, else ``False``.

        A pipe is defined as a block with all but one of its 3 dimensions that are scalable.

        """
        return sum(dim.is_scalable() for dim in self.dimensions) == 2

    @property
    def is_temporal_pipe(self) -> bool:
        """Return ``True`` if ``self`` is a temporal pipe, else ``False``.

        A temporal pipe is a pipe (exactly 2 scalable dimensions) for which the non-scalable
        dimension is the third one (time dimension).

        """
        return self.is_pipe and self.dimensions[2].is_constant()

    def __eq__(self, value: object) -> bool:
        return isinstance(value, Block) and super().__eq__(value)

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")


def merge_parallel_block_layers(
    blocks_in_parallel: Mapping[LayoutPosition2D, Block],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> list[LayoutLayer | BaseComposedLayer]:
    """Merge several stacks of layers executed in parallel into one stack of larger layers.

    Args:
        blocks_in_parallel: a 2-dimensional arrangement of blocks. Each of the
            provided block MUST have the exact same duration (also called
            "temporal footprint", or number of atomic layers).
        scalable_qubit_shape: scalable shape of a scalable qubit. Considered
            valid across the whole domain.

    Returns:
        a stack of layers representing the same slice of computation as the
        provided ``blocks_in_parallel``.

    Raises:
        TQECError: if two items from the provided ``blocks_in_parallel`` do
            not have the same temporal footprint.
        NotImplementedError: if the provided blocks cannot be merged due to a
            code branch not being implemented yet (and not due to a logical
            error making the blocks unmergeable).

    """
    if not blocks_in_parallel:
        return []
    internal_layers_schedules = frozenset(
        tuple(layer.scalable_timesteps for layer in block.layer_sequence)
        for block in blocks_in_parallel.values()
    )
    if len(internal_layers_schedules) != 1:
        raise NotImplementedError(
            "merge_parallel_block_layers only supports merging blocks that have "
            "layers with a matching temporal schedule. Found the following "
            "different temporal schedules in the provided blocks: "
            f"{internal_layers_schedules}."
        )
    schedule: Final = next(iter(internal_layers_schedules))
    merged_layers: list[LayoutLayer | BaseComposedLayer] = []
    for i in range(len(schedule)):
        layers = {pos: block.layer_sequence[i] for pos, block in blocks_in_parallel.items()}
        if contains_only_base_layers(layers):
            merged_layers.append(
                merge_base_layers(
                    cast(dict[LayoutPosition2D, BaseLayer], layers), scalable_qubit_shape
                )
            )
        elif contains_only_composed_layers(layers):
            merged_layers.append(
                merge_composed_layers(
                    cast(dict[LayoutPosition2D, BaseComposedLayer], layers), scalable_qubit_shape
                )
            )
        else:
            raise RuntimeError(
                f"Found a mix of {BaseLayer.__name__} instances and "
                f"{BaseComposedLayer.__name__} instances in a single temporal "
                f"layer. This should be already checked before. This is a "
                "logical error in the code, please open an issue. Found layers:"
                f"\n{list(layers.values())}"
            )
    return merged_layers
