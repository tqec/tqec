from itertools import chain, repeat
from typing import Final, Iterator, Mapping, Sequence, cast

from tqec.blocks.block import Block
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.atomic.layout import LayoutLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.blocks.layers.composed.repeated import RepeatedLayer
from tqec.blocks.layers.composed.sequenced import SequencedLayers
from tqec.utils.exceptions import TQECException
from tqec.utils.maths import least_common_multiple
from tqec.utils.position import BlockPosition2D, Position3D
from tqec.utils.scale import LinearFunction, round_or_fail


class TopologicalComputationGraph:
    def __init__(self, blocks: Mapping[Position3D, Block] | None = None) -> None:
        if blocks is None:
            blocks = {}
        self._blocks: dict[Position3D, Block] = dict(blocks.items())
        self._min_z: int = min(pos.z for pos in blocks.keys())
        self._max_z: int = max(pos.z for pos in blocks.keys())

    def add_block(self, position: Position3D, block: Block) -> None:
        if position in self._blocks:
            raise TQECException(
                "Cannot override a block with add_block. There is already an "
                f"entry at {position}."
            )
        self._blocks[position] = block
        self._min_z = min(self._min_z, position.z)
        self._max_z = max(self._max_z, position.z)

    @property
    def layout_layers(
        self,
    ) -> Iterator[Sequence[LayoutLayer | BaseComposedLayer[LayoutLayer]]]:
        blocks_by_z: dict[int, dict[BlockPosition2D, Block]] = {
            z: {} for z in range(self._min_z, self._max_z + 1)
        }
        for pos, block in self._blocks.items():
            blocks_by_z[pos.z][pos.as_2d().with_block_coordinate_system()] = block

        for blocks in blocks_by_z.values():
            yield merge_parallel_block_layers(blocks)


def merge_parallel_block_layers(
    blocks_in_parallel: Mapping[BlockPosition2D, Block],
) -> Sequence[LayoutLayer | BaseComposedLayer[LayoutLayer]]:
    """Merge several stacks of layers executed in parallel into one stack of
    larger layers.

    Args:
        blocks_in_parallel: a 2-dimensional arrangement of blocks. Each of the
            provided block MUST have the exact same duration (also called
            "temporal footprint", number of base layers, or height in the Z
            dimension).

    Returns:
        a stack of layers representing the same slice of computation as the
        provided ``blocks_in_parallel``.

    Raises:
        TQECException: if two items from the provided ``blocks_in_parallel`` do
            not have the same temporal footprint.
        NotImplementedError: if two of the provided blocks have layers that do
            not overlap perfectly in time.
    """
    if not blocks_in_parallel:
        return []
    internal_layers_schedules = frozenset(
        tuple(layer.scalable_timesteps for layer in block.layers)
        for block in blocks_in_parallel.values()
    )
    temporal_footprints = frozenset(
        sum(sched, start=LinearFunction(0, 0)) for sched in internal_layers_schedules
    )
    if len(temporal_footprints) != 1:
        raise TQECException(
            "The blocks provided to merge_parallel_block_layers should ALL have "
            "the same temporal footprint. Found the following different "
            f"footprints in the temporal dimension: {temporal_footprints}."
        )
    if len(internal_layers_schedules) != 1:
        raise NotImplementedError(
            "merge_parallel_block_layers only supports merging blocks that have "
            "layers with a matching temporal schedule. Found the following "
            "different temporal schedules in the provided blocks: "
            f"{internal_layers_schedules}."
        )
    schedule: Final = next(iter(internal_layers_schedules))
    merged_layers: list[LayoutLayer | BaseComposedLayer[LayoutLayer]] = []
    for i in range(len(schedule)):
        layers = {pos: block.layers[i] for pos, block in blocks_in_parallel.items()}
        if all(isinstance(layer, BaseLayer) for layer in layers.values()):
            merged_layers.append(
                # Cast needed to make type-checker happy
                _merge_base_layers(cast(dict[BlockPosition2D, BaseLayer], layers))
            )
        else:  # all(isinstance(layer, BaseComposedLayer) for layer in layers.values()):
            merged_layers.append(
                _merge_composed_layers(
                    # Cast needed to make type-checker happy
                    cast(dict[BlockPosition2D, BaseComposedLayer[BaseLayer]], layers)
                )
            )
    return merged_layers


def _merge_base_layers(layers: dict[BlockPosition2D, BaseLayer]) -> LayoutLayer:
    return LayoutLayer(layers)


def _merge_composed_layers(
    layers: dict[BlockPosition2D, BaseComposedLayer[BaseLayer]],
) -> BaseComposedLayer[LayoutLayer]:
    # First, check that all the provided layers have the same scalable timesteps.
    different_timesteps = frozenset(
        layer.scalable_timesteps for layer in layers.values()
    )
    if len(different_timesteps) > 1:
        raise TQECException(
            "Cannot merged BaseComposedLayer instances that have different lengths. "
            f"Found the following different lengths: {different_timesteps}."
        )
    # timesteps = next(iter(different_timesteps))
    if all(isinstance(layer, RepeatedLayer) for layer in layers.values()):
        return _merge_repeated_layers(
            # Cast needed to make type-checker happy.
            cast(dict[BlockPosition2D, RepeatedLayer[BaseLayer]], layers)
        )
    if all(isinstance(layer, SequencedLayers) for layer in layers.values()):
        return _merge_sequenced_layers(
            # Cast needed to make type-checker happy.
            cast(dict[BlockPosition2D, SequencedLayers[BaseLayer]], layers)
        )
    # We are left here with a mix of RepeatedLayer and SequencedLayers.
    # Check that, in case a new subclass of BaseComposedLayer has been introduced.
    if not all(
        isinstance(layer, (RepeatedLayer, SequencedLayers)) for layer in layers.values()
    ):
        unknown_types = {type(layer) for layer in layers.values()} - {
            RepeatedLayer,
            SequencedLayers,
        }
        raise NotImplementedError(
            f"Found instances of {unknown_types} that are not yet implemented "
            "in _merge_composed_layers."
        )
    return _merge_repeated_and_sequenced_layers(
        cast(
            dict[
                BlockPosition2D, SequencedLayers[BaseLayer] | RepeatedLayer[BaseLayer]
            ],
            layers,
        )
    )


def _merge_repeated_layers(
    layers: dict[BlockPosition2D, RepeatedLayer[BaseLayer]],
) -> RepeatedLayer[LayoutLayer]:
    """Merge several RepeatedLayer that should be executed in parallel.

    Args:
        layers: the different repeated layers that should be merged.

    Raises:
        TQECException: if the provided repeated layers do not all have the same
            temporal footprint.
        NotImplementedError: if any of the provided repeated layers have an
            internal layer (i.e., the layer that is being repeated) with a
            non-constant temporal footprint.

    Returns:
        a unique repeated layer implementing the same piece of computation as
        the provided repeated layers.
    """
    # First, check that all the provided layers have the same scalable timesteps.
    different_timesteps = frozenset(
        layer.scalable_timesteps for layer in layers.values()
    )
    if len(different_timesteps) > 1:
        raise TQECException(
            "Cannot merged RepeatedLayer instances that have different lengths. "
            f"Found the following different lengths: {different_timesteps}."
        )
    scalable_timesteps = next(iter(different_timesteps))
    timesteps_per_repetition: dict[BlockPosition2D, int] = {}
    for pos, layer in layers.items():
        timesteps = layer.internal_layer.scalable_timesteps
        # Implementation note: the fact that the internal layer is of constant
        # size in the time dimension is used later in the function.
        if not timesteps.is_constant():
            raise NotImplementedError(
                "Found a RepeatedLayer with a scalable in time internal layer. "
                "This is currently not supported."
            )
        timesteps_per_repetition[pos] = round_or_fail(timesteps.offset)

    # The internal layer of the returned RepeatedLayer should be divisible by
    # all the values in timesteps_per_repetition. Basically we want the smallest
    # integer that is a multiple of each timesteps, i.e., the "least common
    # multiple".
    # Also, `1`s do not have to be accounted for because they are trivially a
    # divisor of any integer.
    considered_timesteps = [
        timesteps for timesteps in timesteps_per_repetition.values() if timesteps > 1
    ]
    # If we only have `1`s (and so considered_timesteps is empty), that's trivial:
    if not considered_timesteps:
        # Sanity check on repetitions
        different_repetitions = frozenset(
            layer.scalable_timesteps for layer in layers.values()
        )
        assert len(different_repetitions) == 1
        # Sanity check on types: SequencedLayer guarantees that it contains at
        # least 2 base layers, so we cannot have any SequencedLayer instance here,
        # meaning that we only have PlaquetteLayer instances.
        return RepeatedLayer(
            _merge_base_layers(
                cast(
                    dict[BlockPosition2D, BaseLayer],
                    {pos: layer.internal_layer for pos, layer in layers.items()},
                )
            ),
            next(iter(different_repetitions)),
        )
    # Else, we need the least common multiple
    num_internal_layers = least_common_multiple(considered_timesteps)
    # And we create sequences of that size and merge them!
    base_sequences: dict[BlockPosition2D, list[BaseLayer]] = {}
    for pos, layer in layers.items():
        internal_layer = layer.internal_layer
        if isinstance(internal_layer, BaseLayer):
            base_sequences[pos] = [internal_layer for _ in range(num_internal_layers)]
        else:
            # We know for sure that the internal layer is of constant size so
            # we can get its layers for any value of k we want.
            layer_sequence = list(internal_layer.all_layers(0))
            base_len = len(layer_sequence)
            internal_repetitions = num_internal_layers // base_len
            base_sequences[pos] = list(
                chain.from_iterable(repeat(layer_sequence, internal_repetitions))
            )
    # Checking post-condition of the above loop.
    assert all(
        len(layer_sequence) == num_internal_layers
        for layer_sequence in base_sequences.values()
    )
    # Computing the new scalable repetitions number.
    # Note that the following should in theory never fail, because all the
    # repeated layers given in input have the SAME scalable shapes, and so in
    # theory num_internal_layers should be a divisor of each of the overall
    # scalable shapes.
    repetitions = scalable_timesteps.exact_integer_div(num_internal_layers)
    return RepeatedLayer(
        SequencedLayers(
            [
                _merge_base_layers(
                    {
                        pos: layer_sequence[i]
                        for pos, layer_sequence in base_sequences.items()
                    }
                )
                for i in range(num_internal_layers)
            ]
        ),
        repetitions,
    )


def _merge_sequenced_layers(
    layers: dict[BlockPosition2D, SequencedLayers[BaseLayer]],
) -> SequencedLayers[LayoutLayer]:
    internal_layers_schedules = frozenset(
        tuple(layer.scalable_timesteps for layer in sequenced_layer.layer_sequence)
        for sequenced_layer in layers.values()
    )
    if len(internal_layers_schedules) != 1:
        raise NotImplementedError(
            "_merge_sequenced_layers only supports merging sequences that have "
            "layers with a matching temporal schedule. Found the following "
            "different temporal schedules in the provided sequences: "
            f"{internal_layers_schedules}."
        )
    internal_layers_schedule = next(iter(internal_layers_schedules))
    merged_layers: list[LayoutLayer | BaseComposedLayer[LayoutLayer]] = []
    for i in range(len(internal_layers_schedule)):
        layers_at_timestep = {
            pos: sequenced_layers.layer_sequence[i]
            for pos, sequenced_layers in layers.items()
        }
        if all(isinstance(layer, BaseLayer) for layer in layers_at_timestep.values()):
            merged_layers.append(
                _merge_base_layers(
                    cast(dict[BlockPosition2D, BaseLayer], layers_at_timestep)
                )
            )
        else:
            # Checking that we only have BaseComposedLayer instances
            assert all(
                isinstance(layer, BaseComposedLayer)
                for layer in layers_at_timestep.values()
            ), "Expected BaseComposedLayer instances."
            merged_layers.append(
                _merge_composed_layers(
                    cast(
                        dict[BlockPosition2D, BaseComposedLayer[BaseLayer]],
                        layers_at_timestep,
                    )
                )
            )
    return SequencedLayers(merged_layers)


def _merge_repeated_and_sequenced_layers(
    layers: dict[
        BlockPosition2D, SequencedLayers[BaseLayer] | RepeatedLayer[BaseLayer]
    ],
) -> SequencedLayers[LayoutLayer]:
    raise NotImplementedError(
        "Merging RepeatedLayer and SequencedLayers is not currently supported."
    )
