"""Split the statistics for multiple observables."""

import collections
from functools import reduce
from typing import Mapping

import sinter

from tqec.computation.correlation import CorrelationSurface, ZXEdge


def split_counts_for_observables(
    counts: Mapping[str, int], num_observables: int
) -> list[int]:
    """Split the error counts for each individual observable when
    specifying ``count_observable_error_combos=True`` for ``sinter``.

    Args:
        counts: The error counts for different observable error combinations.
        num_observables: The number of observables.

    Returns:
        A list of error counts for each individual observable.
    """
    split_counts: list[int] = [0] * num_observables
    for key, count in counts.items():
        if not key.startswith("obs_mistake_mask="):
            continue
        comb = key.split("=")[1]
        assert num_observables == len(comb)
        for i in range(num_observables):
            if comb[i] == "E":
                split_counts[i] += count
    return split_counts


def split_stats_for_observables(
    stats: list[sinter.TaskStats],
    num_observables: int,
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
    stats_by_observables: list[list[sinter.TaskStats]] = [
        [] for _ in range(num_observables)
    ]
    for task_stats in combined_stats:
        split_counts = split_counts_for_observables(
            task_stats.custom_counts, num_observables
        )
        for obs_idx, count in enumerate(split_counts):
            stats_by_observables[obs_idx].append(
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
    return stats_by_observables


def heuristic_custom_error_key(observables: list[CorrelationSurface]) -> str:
    """Get a heuristic custom error key using for the ``error`` metric in
    ``sinter``.

    Currently, we determine the most likely observable error combinations by
    analyzing their correlation surfaces. For each combination, we perform an
    AND on the corresponding correlation surfaces and calculate the area of the
    resulting span. We then rank these combinations according to the computed
    AND-area metric. To derive a reasonable error metric, we select
    ``ordered_combs[-len(observables)]`` for two reasons: first, errors should
    be easy to sample so as not to require excessive shots; and second, once an
    error reaches a preset MAX value, there should be enough statistical data for
    all individual observables.

    Args:
        observables: The list of observables.

    Returns:
        The heuristic custom error key.
    """
    key_area: dict[str, int] = {}
    span_union: set[ZXEdge] = reduce(
        lambda a, b: a | b,
        (obs.span for obs in observables),
        set(),
    )
    for edge in span_union:
        key_list: list[str] = []
        for obs in observables:
            key_list.append("E" if edge in obs.span else "_")
        key = "obs_mistake_mask=" + "".join(key_list)
        key_area[key] = key_area.get(key, 0) + 1
    most_frequent_keys = sorted(key_area.items(), key=lambda x: x[1])
    return most_frequent_keys[-len(observables)][0]
