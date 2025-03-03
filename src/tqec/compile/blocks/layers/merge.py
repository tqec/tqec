from itertools import chain, repeat
from typing import Final, Mapping, TypeGuard

import numpy

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import PhysicalQubitScalable2D, round_or_fail

# Note on the few functions below:
# These functions are needed mostly for typing purposes. The main issue is that
# all the type-checkers I tested are not able to infer the correct type in the
# situation below:
#
# obj: dict[int, int | float] = {}
# if all(isinstance(value, float) for value in obj.values()):
#     # We expect obj to be "dict[int, float]", but type checkers are not able
#     # to infer that.
#
# To circumvent that, the functions below use typing.TypeGuard (see
# https://docs.python.org/3/library/typing.html#typing.TypeGuard).


def _contains_only_base_layers(
    layers: dict[LayoutPosition2D, BaseLayer | BaseComposedLayer],
) -> TypeGuard[dict[LayoutPosition2D, BaseLayer]]:
    return all(isinstance(layer, BaseLayer) for layer in layers.values())


def _contains_only_composed_layers(
    layers: dict[LayoutPosition2D, BaseLayer | BaseComposedLayer],
) -> TypeGuard[dict[LayoutPosition2D, BaseComposedLayer]]:
    return all(isinstance(layer, BaseComposedLayer) for layer in layers.values())


def _contains_only_repeated_layers(
    layers: dict[LayoutPosition2D, BaseComposedLayer],
) -> TypeGuard[dict[LayoutPosition2D, RepeatedLayer]]:
    return all(isinstance(layer, RepeatedLayer) for layer in layers.values())


def _contains_only_sequenced_layers(
    layers: dict[LayoutPosition2D, BaseComposedLayer],
) -> TypeGuard[dict[LayoutPosition2D, SequencedLayers]]:
    return all(isinstance(layer, SequencedLayers) for layer in layers.values())


def _contains_only_repeated_or_sequenced_layers(
    layers: dict[LayoutPosition2D, BaseComposedLayer],
) -> TypeGuard[dict[LayoutPosition2D, SequencedLayers | RepeatedLayer]]:
    return all(
        isinstance(layer, (SequencedLayers, RepeatedLayer)) for layer in layers.values()
    )


def merge_parallel_block_layers(
    blocks_in_parallel: Mapping[LayoutPosition2D, Block],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> list[LayoutLayer | BaseComposedLayer]:
    """Merge several stacks of layers executed in parallel into one stack of
    larger layers.

    Args:
        blocks_in_parallel: a 2-dimensional arrangement of blocks. Each of the
            provided block MUST have the exact same duration (also called
            "temporal footprint", number of base layers, or height in the Z
            dimension).
        scalable_qubit_shape: scalable shape of a scalable qubit. Considered
            valid across the whole domain.

    Returns:
        a stack of layers representing the same slice of computation as the
        provided ``blocks_in_parallel``.

    Raises:
        TQECException: if two items from the provided ``blocks_in_parallel`` do
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
        layers = {
            pos: block.layer_sequence[i] for pos, block in blocks_in_parallel.items()
        }
        if _contains_only_base_layers(layers):
            merged_layers.append(_merge_base_layers(layers, scalable_qubit_shape))
        elif _contains_only_composed_layers(layers):
            merged_layers.append(_merge_composed_layers(layers, scalable_qubit_shape))
        else:
            raise RuntimeError(
                f"Found a mix of {BaseLayer.__name__} instances and "
                f"{BaseComposedLayer.__name__} instances in a single temporal "
                f"layer. This should be already checked before. This is a "
                "logical error in the code, please open an issue. Found layers:"
                f"\n{list(layers.values())}"
            )
    return merged_layers


def _merge_base_layers(
    layers: dict[LayoutPosition2D, BaseLayer],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> LayoutLayer:
    return LayoutLayer(layers, scalable_qubit_shape)


def _merge_composed_layers(
    layers: dict[LayoutPosition2D, BaseComposedLayer],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> BaseComposedLayer:
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
    if _contains_only_repeated_layers(layers):
        return _merge_repeated_layers(layers, scalable_qubit_shape)
    if _contains_only_sequenced_layers(layers):
        return _merge_sequenced_layers(layers, scalable_qubit_shape)
    # We are left here with a mix of RepeatedLayer and SequencedLayers.
    # Check that, in case a new subclass of BaseComposedLayer has been introduced.
    if not _contains_only_repeated_or_sequenced_layers(layers):
        unknown_types = {type(layer) for layer in layers.values()} - {
            RepeatedLayer,
            SequencedLayers,
        }
        raise NotImplementedError(
            f"Found instances of {unknown_types} that are not yet implemented "
            "in _merge_composed_layers."
        )
    return _merge_repeated_and_sequenced_layers(layers, scalable_qubit_shape)


def _merge_repeated_layers(
    layers: dict[LayoutPosition2D, RepeatedLayer],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> RepeatedLayer:
    """Merge several RepeatedLayer that should be executed in parallel.

    Args:
        layers: the different repeated layers that should be merged.
        scalable_qubit_shape: scalable shape of a scalable qubit. Considered
            valid across the whole domain.

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
            "Cannot merge RepeatedLayer instances that have different lengths. "
            f"Found the following different lengths: {different_timesteps}."
        )
    scalable_timesteps = next(iter(different_timesteps))
    timesteps_per_repetition: dict[LayoutPosition2D, int] = {}
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
        inner_layers = {pos: layer.internal_layer for pos, layer in layers.items()}
        assert _contains_only_base_layers(inner_layers)
        return RepeatedLayer(
            _merge_base_layers(inner_layers, scalable_qubit_shape),
            next(iter(different_repetitions)),
        )
    # Else, we need the least common multiple
    num_internal_layers = numpy.lcm.reduce(considered_timesteps)
    # And we create sequences of that size to merge them!
    base_sequences: dict[LayoutPosition2D, list[BaseLayer]] = {}
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
                    },
                    scalable_qubit_shape,
                )
                for i in range(num_internal_layers)
            ]
        ),
        repetitions,
    )


def _merge_sequenced_layers(
    layers: dict[LayoutPosition2D, SequencedLayers],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> SequencedLayers:
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
    merged_layers: list[LayoutLayer | BaseComposedLayer] = []
    for i in range(len(internal_layers_schedule)):
        layers_at_timestep = {
            pos: sequenced_layers.layer_sequence[i]
            for pos, sequenced_layers in layers.items()
        }
        if _contains_only_base_layers(layers_at_timestep):
            merged_layers.append(
                _merge_base_layers(layers_at_timestep, scalable_qubit_shape)
            )
        elif _contains_only_composed_layers(layers_at_timestep):
            merged_layers.append(
                _merge_composed_layers(layers_at_timestep, scalable_qubit_shape)
            )
        else:
            raise RuntimeError(
                f"Found a mix of {BaseLayer.__name__} instances and "
                f"{BaseComposedLayer.__name__} instances in a single temporal "
                f"layer. This should be already checked before. This is a "
                "logical error in the code, please open an issue. Found layers:"
                "\n - "
                + "\n - ".join(repr(layer) for layer in layers_at_timestep.values())
            )
    return SequencedLayers(merged_layers)


def _merge_repeated_and_sequenced_layers(
    layers: dict[LayoutPosition2D, SequencedLayers | RepeatedLayer],
    scalable_qubit_shape: PhysicalQubitScalable2D,
) -> SequencedLayers:
    """Merge composed layers with both RepeatedLayer and SequencedLayers instances.

    Raises:
        TQECException: if there is no layer of type SequencedLayers.
        TQECException: if there is no layer of type RepeatedLayer.
        TQECException: if the provided layers have different durations.
        NotImplementedError: if the ScheduledLayers instances in ``layers`` have
            different schedules.
    """
    layer_types = frozenset(type(layer) for layer in layers.values())
    if layer_types != frozenset((RepeatedLayer, SequencedLayers)):
        raise TQECException(
            "Wrong layer types: expecting at least one layer for each of the "
            f"expected types ({RepeatedLayer.__name__} and {SequencedLayers.__name__}) "
            "but got the following types: " + ",".join(t.__name__ for t in layer_types)
        )
    different_timesteps = frozenset(
        layer.scalable_timesteps for layer in layers.values()
    )
    if len(different_timesteps) > 1:
        raise TQECException(
            f"Cannot merge {RepeatedLayer.__name__} and {SequencedLayers.__name__} "
            "instances that have different durations. Found the following "
            f"different durations: {different_timesteps}."
        )
    sequenced_schedules = frozenset(
        layer.schedule
        for layer in layers.values()
        if isinstance(layer, SequencedLayers)
    )
    if len(sequenced_schedules) != 1:
        raise NotImplementedError(
            f"Merging different {SequencedLayers.__name__} instances with different "
            "schedules is not implemented yet. Found the following schedules: "
            f"{sequenced_schedules}."
        )
    schedule = next(iter(sequenced_schedules))
    return _merge_sequenced_layers(
        {
            pos: layer.to_sequenced_layer_with_schedule(schedule)
            for pos, layer in layers.items()
        },
        scalable_qubit_shape,
    )
