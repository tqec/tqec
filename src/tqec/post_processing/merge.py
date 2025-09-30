from __future__ import annotations

import stim

from tqec.circuit.moment import Moment
from tqec.post_processing.remove import _remove_empty_moments_inline
from tqec.post_processing.utils.moment import (
    RepeatedMoments,
    collect_moments,
    iter_stim_circuit_by_moments,
    merge_moments,
)


def merge_adjacent_moments(circuit: stim.Circuit) -> stim.Circuit:
    """Merge adjacent moments that can be merged.

    This function merges moments from the provided ``circuit`` that can be
    merged together. It performs merging in the increasing time direction. It
    may re-organise the neighbourhood of ``REPEAT`` blocks in some cases, but
    the returned circuit should always be strictly equivalent to the provided
    one.

    Args:
        circuit: a circuit containing moments that may be mergeable.

    Returns:
        a new quantum circuit that contains strictly the same instructions as
        the provided ``circuit`` but that might re-order some of these operations
        to reduce the number of moments.

    """
    merged_moments: list[Moment | RepeatedMoments] = list(
        iter_stim_circuit_by_moments(circuit, collected_before_use=True)
    )
    _remove_empty_moments_inline(merged_moments)
    modification_performed: bool = True
    while modification_performed:
        modification_performed = False
        modification_performed |= _merge_internal_adjacent_moments_inline(merged_moments)
        modification_performed |= _merge_repeat_block_boundaries_inline(merged_moments)
    return collect_moments(merged_moments)


def _can_be_merged(lhs: Moment, rhs: Moment) -> bool:
    return not lhs.qubits_indices.intersection(rhs.qubits_indices)


def _merge_internal_adjacent_moments_inline(
    moments: list[Moment | RepeatedMoments],
) -> bool:
    """Merge adjacent moments without considering REPEAT block boundaries.

    Returns:
        ``True`` if the provided ``moments`` have been modified, else ``False``.

    """
    i: int = 1
    modification_performed: bool = False
    while i < len(moments):
        # Invariant of the loop: moments[i - 1] is not a REPEAT block.
        previous_moment, current_moment = moments[i - 1], moments[i]
        assert not isinstance(previous_moment, RepeatedMoments)

        if isinstance(current_moment, RepeatedMoments):
            # Just recurse in the REPEAT block but do not perform any specific
            # computation for its boundaries.
            modification_performed |= _merge_internal_adjacent_moments_inline(
                current_moment.moments
            )
            # We do not have to look at the moment just after the REPEAT block
            # because it will not be merged with the REPEAT block, so just skip
            # it (that also allows to respect the loop invariant).
            i += 2
            continue

        # Try to merge moments[i] into moments[i - 1]
        # If they can be merged, merge them. Else, just increase i and go to the
        # next moment.
        if _can_be_merged(previous_moment, current_moment):
            moments[i - 1] = merge_moments(previous_moment, current_moment)
            moments.pop(i)
            modification_performed = True
        else:
            i += 1
    return modification_performed


def _merge_repeat_block_boundaries_inline(
    moments: list[Moment | RepeatedMoments],
) -> bool:
    i: int = 0
    modification_performed: bool = False
    while i < len(moments):
        current_moment = moments[i]
        if not isinstance(current_moment, RepeatedMoments):
            i += 1
            continue
        # First recursively merge the potentially nested REPEAT blocks boundaries.
        modification_performed |= _merge_repeat_block_boundaries_inline(current_moment.moments)
        # Then merge the boundaries of the current REPEAT block if possible.
        start, *bulk, end = current_moment.moments
        if isinstance(start, RepeatedMoments) or isinstance(end, RepeatedMoments):
            # Not handled yet, just ignore.
            i += 1
            continue
        if not _can_be_merged(start, end) or current_moment.repetitions < 2:
            # Either START and END cannot be merged or merging them would lead to
            # an invalid REPEAT block (repetitions == 0), so do nothing.
            i += 1
            continue
        # Here, we know that start and start can be merged. We replace:
        #
        # REPEAT N {
        #     START
        #     BULK
        #     END
        # }
        #
        # by
        #
        # START
        # BULK
        # REPEAT N - 1 {
        #     END + START
        #     BULK
        # }
        # END
        # Note: modifying moments in-place.
        moments.pop(i)
        new_repeat_block = RepeatedMoments(
            current_moment.repetitions - 1, [merge_moments(end, start), *bulk]
        )
        inserted_moments = [start, *bulk, new_repeat_block, end]
        for m in range(len(inserted_moments)):
            moments.insert(i + m, inserted_moments[m])
        modification_performed = True
        # We can update i to the index of the REPEAT block, just in case more
        # merging can be done. Note that even if BULK contains REPEAT blocks,
        # they have been addressed in the beginning of this loop iteration, hence
        # we do not need to iterate again on BULK.
        i += len(bulk) + 1
    return modification_performed
