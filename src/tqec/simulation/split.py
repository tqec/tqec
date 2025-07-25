"""Split the statistics for multiple observables."""

import collections
from collections.abc import Mapping

import sinter

# Import of a private module not marked as explicitly typed, type ignore for mypy.
from sinter._data import ExistingData  # type: ignore

from tqec.computation.correlation import CorrelationSurface


def split_counts_for_observables(counts: Mapping[str, int], num_observables: int) -> list[int]:
    """Split the error counts for each individual observable.

    This function should only be used when specifying ``count_observable_error_combos=True`` to
    ``sinter`` functions.

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
    """Split the statistics for each individual observable.

    This function should only be used when specifying ``count_observable_error_combos=True`` to
    ``sinter`` functions.

    Args:
        stats: The statistics for different observable error combinations.
        num_observables: number of observables contained in the provided ``stats``.

    Returns:
        A list of statistics for each individual observable.

    """
    # Combine the stats for each task
    data = ExistingData()
    for s in stats:
        data.add_sample(s)
    combined_stats = list(data.data.values())

    # For each task, split the stats by observable
    stats_by_observables: list[list[sinter.TaskStats]] = [[] for _ in range(num_observables)]
    for task_stats in combined_stats:
        split_counts = split_counts_for_observables(task_stats.custom_counts, num_observables)
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
    """Get a heuristic custom error key using for the ``error`` metric in ``sinter``.

    To get the statistics for each individual observable, we set
    ``count_observable_error_combos=True`` in ``sinter.collect``. It will include
    error counts for each observable error combination in the stats. For example,
    ``{'obs_mistake_mask=EE_': 10, 'obs_mistake_mask=E_E': 20}`` means that 10
    errors flipped both the first and second observables, and 20 errors flipped
    both the first and third observables, are sampled. We then split the counts
    to get the error counts for each individual observable.

    By default, ``sinter`` will count an error that flips any number of observables
    as a single error in the stats. As we want to sample enough statistics for
    each individual observable, which might have large variance in the logical
    error rate, we need to select a good ``custom_error_count_key``.

    Firstly we find the observable with the minimum error rate, which is expected
    to be the observable with the minimal correlation surface area. If we ensure
    this observable has enough statistical data, we can ensure all the observables
    have enough data. Therefore, we need to find all the observable combinations
    that contains this observable. Then we order the combinations by their
    probabilities, and return the most frequent one as the heuristic custom error
    key, which needs the least shots to achieve a set ``max_errors``. The final
    key will be in the form like ``obs_mistake_mask=EE_``, where `EE_` will be
    substituted by the actual observable combination.

    We estimate the probabilities of each possible observable combination by
    studying their correlation surfaces. Consider the correlation surfaces of
    some observables, an error chain crossing some fragment of correlation surface
    can flip all the observables iff. the fragment belongs to all the correlation
    surfaces, i.e. the intersection (AND) of the correlation surfaces. For each
    fragment, we find all the observables that contain it and generate the
    combination key. We then increase the frequency of the key, which means a
    single error chain at the fragment can flip all the observables. We use the
    number of fragments that can flip a observable comb as the proxy of the
    probability of the observable comb.

    Args:
        observables: The list of observables.

    Returns:
        The heuristic custom error key.

    """
    # observable with minimal correlation surface area
    minimal_area_obs = min(observables, key=lambda x: x.area())

    # Estimate the probabilities of each observable combination that contains
    # the least frequent observable
    obs_comb_to_prob: dict[str, int] = {}
    for fragment in minimal_area_obs.span:
        obs_comb: list[str] = ["E" if fragment in obs.span else "_" for obs in observables]
        key = "obs_mistake_mask=" + "".join(obs_comb)
        obs_comb_to_prob[key] = obs_comb_to_prob.get(key, 0) + 1
    # return the most frequent observable combination
    return max(obs_comb_to_prob.keys(), key=lambda x: obs_comb_to_prob[x])
