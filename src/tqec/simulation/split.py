"""Split the statistics for multiple observables."""

import collections
from typing import Mapping

import sinter


def split_counts_for_observables(counts: Mapping[str, int]) -> list[int]:
    """Split the error counts for each individual observable when
    specifying ``count_observable_error_combos=True`` for ``sinter``.

    Args:
        counts: The error counts for different observable error combinations.

    Returns:
        A list of error counts for each individual observable.
    """
    num_observables: int = 0
    split_counts: list[int] = []
    for key, count in counts.items():
        if not key.startswith("obs_mistake_mask="):
            continue
        comb = key.split("=")[1]
        if num_observables == 0:
            num_observables = len(comb)
            split_counts = [0] * num_observables
        assert num_observables == len(comb)
        for i in range(num_observables):
            if comb[i] == "E":
                split_counts[i] += count

    if num_observables == 0:
        raise ValueError("No observable mistake mask found in the counts.")
    return split_counts


def split_stats_for_observables(
    stats: list[sinter.TaskStats],
) -> list[list[sinter.TaskStats]]:
    """Split the statistics for each individual observable when specifying
    ``count_observable_error_combos=True`` for ``sinter``.

    Args:
        stats: The statistics for different observable error combinations.

    Returns:
        A list of statistics for each individual observable.
    """
    from sinter._data import ExistingData  # type: ignore

    # Combine the stats for each task
    data = ExistingData()
    for s in stats:
        data.add_sample(s)
    combined_stats = list(data.data.values())

    # For each task, split the stats by observable
    stats_by_observables: dict[int, list[sinter.TaskStats]] = {}
    for task_stats in combined_stats:
        split_counts = split_counts_for_observables(task_stats.custom_counts)
        for obs_idx, count in enumerate(split_counts):
            stats_by_observables.setdefault(obs_idx, []).append(
                task_stats.with_edits(
                    errors=count,
                    custom_counts=collections.Counter(
                        {
                            k: v
                            for k, v in task_stats.custom_counts.items()
                            if not k.startswith("obs_mistake_mask=")
                        }
                    ),
                )
            )
    return [stats_by_observables[i] for i in range(len(stats_by_observables))]
