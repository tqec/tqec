import multiprocessing
from collections.abc import Callable, Iterable, Sequence
from math import isclose
from typing import TypeGuard

import sinter

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION, Convention
from tqec.compile.detectors.database import DetectorDatabase
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.utils.exceptions import TQECError
from tqec.utils.noise_model import NoiseModel


def _is_only_floats(seq: Sequence[float | None]) -> TypeGuard[Sequence[float]]:
    return not any(elem is None for elem in seq)


def _is_sorted(seq: Sequence[int | float]) -> bool:
    if not seq:
        return True
    val = seq[0]
    for i in range(1, len(seq)):
        if seq[i] < val:
            return False
        val = seq[i]
    return True


def get_logical_error_rate_per_shot(
    stat: sinter.TaskStats, max_likelihood_factor: float = 1e3
) -> sinter.Fit:
    """Estimates the logical error rate per shot for the given ``stat``.

    Note:
        This function is heavily inspired from an internal function defined in
        ``sinter._plotting.plot_error_rate``.

    Args:
        stat: the statistics to use in order to compute the logical error rate
            per shot.
        max_likelihood_factor: Controls how wide the uncertainty highlight region
            around curves is. Must be 1 or larger. Hypothesis probabilities at
            most that many times as unlikely as the max likelihood hypothesis
            will be highlighted. Forwarded to ``sinter.fit_binomial``.

    Returns:
        The estimation of the logical error rate per shot with appropriate error
        bars.

    """
    result = sinter.fit_binomial(
        num_shots=stat.shots - stat.discards,
        num_hits=stat.errors,
        max_likelihood_factor=max_likelihood_factor,
    )
    if stat.errors == 0:
        result = sinter.Fit(low=result.low, high=result.high, best=float("nan"))

    return result


def binary_search_threshold(
    block_graph: BlockGraph,
    observable: CorrelationSurface,
    noise_model_factory: Callable[[float], NoiseModel],
    minp: float = 1e-5,
    maxp: float = 0.1,
    ks: Sequence[int] = (1, 2),
    atol: float = 1e-4,
    rtol: float = 1e-4,
    manhattan_radius: int = 2,
    convention: Convention = FIXED_BULK_CONVENTION,
    detector_database: DetectorDatabase | None = None,
    num_workers: int = multiprocessing.cpu_count(),
    max_shots: int = 10_000_000,
    max_errors: int = 5_000,
    decoders: Iterable[str] = ("pymatching",),
) -> tuple[float, dict[int, list[tuple[float, sinter.Fit]]]]:
    """Search the threshold value for the provided ``observable`` on the provided ``block_graph``.

    This function performs a binary search on the noise strength (called ``p`` in
    the following explanation) that is commonly called "threshold" in quantum
    error correction.

    The threshold is defined as the noise strength ``p`` below which increasing
    the code distance improves the logical error rate.

    Note:
        For high values of ``p``, the logical error-rate of an observable will
        be very close to ``0.5``, which means that the code is completely unable
        to correct the errors introduced by the operations it requires to work.
        In order to avoid this regime, the binary search will consider that any
        value of ``p`` that leads to logical error-rates above ``0.4`` for all
        the provided ``ks`` is too high (and so recurse the binary search in the
        first half of the interval).

    Warning:
        Small values for ``atol`` and ``rtol`` make very little sense here.

        Due to finite sampling, logical error-rate estimations will not be exact
        and will have error bars. This function does not take these error bars
        into account yet and only uses the best estimate.

        Setting ``atol`` or ``rtol`` to very small values will give the
        impression that the output estimate is very precise, but the noise
        floor imposed by ``max_shots`` and the associated sampling error will
        still be present, and might be higher than ``atol`` and ``rtol``.

    Args:
        block_graph: a representation of the QEC computation to find the
            threshold of.
        observable: the observable that should be considered to find the
            threshold.
        noise_model_factory: a callable that is used to instantiate a noise
            model from the values of ``p`` that are explored by this function.
        minp: lower bound for the threshold value.
        maxp: upper bound for the threshold value.
        ks: values of the scaling parameter `k` to use in order to generate the
            circuits.
        atol: absolute tolerance used to compare the lower and upper bounds
            during the binary search. The search ends when these bounds are
            considered equal w.r.t. the provided ``atol`` and ``rtol``.
        rtol: relative tolerance used to compare the lower and upper bounds
            during the binary search. The search ends when these bounds are
            considered equal w.r.t. the provided ``atol`` and ``rtol``.
        manhattan_radius: radius used to automatically compute detectors. The
            best value to set this argument to is the minimum integer such that
            flows generated from any given reset/measurement, from any plaquette
            at any spatial/temporal place in the QEC computation, do not
            propagate outside of the qubits used by plaquettes spatially located
            at maximum `manhattan_radius` plaquettes from the plaquette the
            reset/measurement belongs to (w.r.t. the Manhattan distance).
            Default to 2, which is sufficient for regular surface code. If
            negative, detectors are not computed automatically and are not added
            to the generated circuits.
        convention: convention used to generate the quantum circuits.
        detector_database: an instance to retrieve from / store in detectors
            that are computed as part of the circuit generation.
        num_workers: The number of worker processes to use.
        max_shots: Defaults to None (unused). Stops the sampling process
            after this many samples have been taken from the circuit.
        max_errors: Defaults to None (unused). Stops the sampling process
            after this many errors have been seen in samples taken from the
            circuit. The actual number sampled errors may be larger due to
            batching.
        decoders: Defaults to None (specified by each Task). The names of the
            decoders to use on each Task. It must either be the case that each
            Task specifies a decoder and this is set to None, or this is an
            iterable and each Task has its decoder set to None.

    Returns:
        A tuple containing an estimation of the threshold and a collection of all
        the logical error-rates computed while searching the threshold

    """
    compiled_graph = compile_block_graph(block_graph, convention, [observable])
    ks = tuple(sorted(ks))
    noiseless_circuits = [
        compiled_graph.generate_stim_circuit(
            k, manhattan_radius=manhattan_radius, detector_database=detector_database
        )
        for k in ks
    ]
    computed_logical_errors: dict[int, list[tuple[float, sinter.Fit]]] = {k: [] for k in ks}
    while not isclose(minp, maxp, rel_tol=rtol, abs_tol=atol):
        midp = (minp + maxp) / 2
        noise_model = noise_model_factory(midp)
        stats = sinter.collect(
            num_workers=num_workers,
            tasks=[
                sinter.Task(
                    circuit=noise_model.noisy_circuit(circ),
                    json_metadata={"d": 2 * k + 1, "r": 2 * k + 1, "p": midp},
                )
                for k, circ in zip(ks, noiseless_circuits)
            ],
            max_shots=max_shots,
            max_errors=max_errors,
            decoders=decoders,
            hint_num_tasks=len(ks),
        )
        logical_errors_fits: list[sinter.Fit] = [
            get_logical_error_rate_per_shot(stat)
            for stat in sorted(stats, key=lambda s: s.json_metadata["d"])
        ]
        # Update computed_logical_errors
        for i, k in enumerate(ks):
            computed_logical_errors[k].append((midp, logical_errors_fits[i]))
        logical_errors: list[float | None] = [lerr_fit.best for lerr_fit in logical_errors_fits]
        if not _is_only_floats(logical_errors):
            raise TQECError(
                "One of the computed logical errors is None. That likely means "
                "that you need more shots in order to have at least a few errors "
                "on all the simulations."
            )
        if all(lerr is not None and lerr > 0.4 for lerr in logical_errors):
            # The physical error rate is too high and the logical error rate
            # saturates around 0.5, so lower maxp
            maxp = midp
        elif _is_sorted([lerr for lerr in logical_errors if lerr is not None]):
            # The smaller k is, the smaller the logical error rate is. That means
            # that midp is above the threshold.
            maxp = midp
        elif _is_sorted([lerr for lerr in logical_errors if lerr is not None][::-1]):
            # The smaller k is, the larger the logical error rate is. That means
            # that midp is below the threshold.
            minp = midp
        else:
            # There is no clear ordering, that means that:
            # 1. the user provided 3 or more values for k,
            # 2. the current midp value is in the transition zone: some
            #    distances (i.e., values of k) are sub-threshold, others are
            #    still above.
            # Returning now seems like the best move.
            break
    return (minp + maxp) / 2, computed_logical_errors
