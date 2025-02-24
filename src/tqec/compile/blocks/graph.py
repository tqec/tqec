"""Defines :class:`TopologicalComputationGraph` that represents a topological
computation.

## Design choices

A few choices have been made during the design phase of this code, and they
deeply impact the public interface. This section explains what are those choices
and why they have been made.

### Substitution VS removal

Before the introduction of :mod:`tqec.compile.blocks`, junctions (or pipes) were
never strictly instantiated in any public-facing data-structure. Internally, the
junction implementation was instantiated but was directly used to **replace**
plaquettes from the 2 blocks that were touched by the junction. This replacement
was encoded as a "substitution" that was a mapping from (potentially negative)
layer indices to a mapping of plaquettes (i.e., a mapping from indices found in
template instantiation to :class:`~tqec.plaquette.plaquette.Plaquette` instances).

This implementation is correct and worked for a moment, but is strictly less
capable than the chosen implementation in this module.

In this module, junctions are instantiated as
:class:`~tqec.compile.blocks.block.Block` instances, just like cubes, and the
neighbouring cubes have their corresponding boundary being stripped off.
That is exactly equivalent to performing a substitution in the case where each
of the 2 cubes and the junction are represented by templates and plaquettes. But
this method also allows to arbitrary mix cube and junction implementations
without requiring all of them to use templates and plaquettes.

Basically, the junction could potentially be implemented using a scalable raw
quantum circuit, and it would work just fine* with any implementation of the
neighbouring cubes.

*: some care should be used for the qubits on the corner between a junction in
the time dimension and one in the space dimension.

For this reason, this module implements the "removal" technique rather than the
substitution one.
"""

from itertools import chain, repeat
from typing import Final, Iterator, Mapping, Sequence, cast

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.enums import border_from_signed_direction
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import LayoutPosition2D, LayoutPosition3D
from tqec.utils.exceptions import TQECException
from tqec.utils.maths import least_common_multiple
from tqec.utils.position import (
    BlockPosition2D,
    BlockPosition3D,
    Direction3D,
    SignedDirection3D,
)
from tqec.utils.scale import LinearFunction, round_or_fail


class TopologicalComputationGraph:
    MAX_VALUE: Final[int] = 2**64

    def __init__(self) -> None:
        """Represents a topological computation with
        :class:`~tqec.compile.blocks.block.Block` instances."""
        self._blocks: dict[LayoutPosition3D, Block] = {}
        self._min_z: int = TopologicalComputationGraph.MAX_VALUE
        self._max_z: int = -TopologicalComputationGraph.MAX_VALUE

    @staticmethod
    def is_valid_position(pos: BlockPosition3D) -> bool:
        return all(
            -TopologicalComputationGraph.MAX_VALUE
            < coord
            < TopologicalComputationGraph.MAX_VALUE
            for coord in pos.as_tuple()
        )

    @staticmethod
    def assert_is_valid_position(pos: BlockPosition3D) -> None:
        if not TopologicalComputationGraph.is_valid_position(pos):
            raise TQECException(
                f"The provided position ({pos}) is invalid. One of its "
                "coordinates is not in ``(-2**64, 2**64)``."
            )

    def add_cube(self, position: BlockPosition3D, block: Block) -> None:
        self.assert_is_valid_position(position)
        layout_position = LayoutPosition3D.from_block_position(position)
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a block with add_block. There is already an "
                f"entry at {layout_position}."
            )
        self._blocks[layout_position] = block
        self._min_z = min(self._min_z, layout_position.z_ordering)
        self._max_z = max(self._max_z, layout_position.z_ordering)

    def _check_junction(self, source: BlockPosition3D, sink: BlockPosition3D) -> None:
        self.assert_is_valid_position(source)
        self.assert_is_valid_position(sink)
        if not source.is_neighbour(sink):
            raise TQECException(
                f"Trying to add a junction between {source} and {sink} that are "
                "not neighbouring positions."
            )
        if not source < sink:
            raise TQECException(
                f"Trying to add a junction between {source:=} and {sink:=} that "
                "are not correctly ordered. The following should be verified: "
                "source < sink."
            )
        layout_position = LayoutPosition3D.from_junction_position((source, sink))
        if layout_position in self._blocks:
            raise TQECException(
                "Cannot override a junction with add_junction. There is already "
                f"a junction at {layout_position}."
            )

    def _trim_junctioned_cubes(
        self, source: BlockPosition3D, sink: BlockPosition3D
    ) -> None:
        self._check_junction(source, sink)
        junction_direction = Direction3D.from_neighbouring_positions(source, sink)
        source_pos = LayoutPosition3D.from_block_position(source)
        sink_pos = LayoutPosition3D.from_block_position(sink)
        self._blocks[source_pos] = self._blocks[source_pos].with_borders_trimmed(
            [border_from_signed_direction(SignedDirection3D(junction_direction, True))]
        )
        self._blocks[sink_pos] = self._blocks[sink_pos].with_borders_trimmed(
            [border_from_signed_direction(SignedDirection3D(junction_direction, False))]
        )

    def add_junction(
        self, source: BlockPosition3D, sink: BlockPosition3D, block: Block
    ) -> None:
        self._trim_junctioned_cubes(source, sink)
        self._blocks[LayoutPosition3D.from_junction_position((source, sink))] = block
        # There is no need to update {min,max}_z because we checked that the
        # junction is applied between two existing cubes when calling
        # _trim_junctioned_cubes, and these two cubes have already potentially
        # updated {min,max}_z

    @property
    def layout_layers(
        self,
    ) -> Iterator[Sequence[LayoutLayer | BaseComposedLayer[LayoutLayer]]]:
        blocks_by_z: dict[int, dict[LayoutPosition2D, Block]] = {
            z: {} for z in range(self._min_z, self._max_z + 1)
        }
        for pos, block in self._blocks.items():
            blocks_by_z[pos.z_ordering][pos.as_2d()] = block

        for blocks in blocks_by_z.values():
            yield merge_parallel_block_layers(blocks)


def merge_parallel_block_layers(
    blocks_in_parallel: Mapping[LayoutPosition2D, Block],
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
