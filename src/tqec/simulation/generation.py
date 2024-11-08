import functools
import itertools
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Iterable, Iterator

import sinter
import stim

from tqec.compile.compile import CompiledGraph
from tqec.noise_model import NoiseModel


def _parallel_func(
    kp: tuple[int, float],
    *,
    compiled_graph: CompiledGraph,
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
) -> tuple[stim.Circuit, int, float]:
    k, p = kp
    noise_model = noise_model_factory(p)
    return (
        compiled_graph.generate_stim_circuit(
            k, noise_model, manhattan_radius=manhattan_radius
        ),
        k,
        p,
    )


def generate_stim_circuits_with_detectors(
    compiled_graph: CompiledGraph,
    ks: Iterable[int],
    ps: Iterable[float],
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
    max_workers: int | None = None,
) -> Iterator[tuple[stim.Circuit, int, float]]:
    """Generate stim circuits in parallel.

    This function generate the `stim.Circuit` instances for all the combinations
    of the given `ks` and `ps` with a noise model that depends on `p` and
    computed with `noise_model_factory`.

    It is equivalent to:

    .. code-block:: python

        for p in ps:
            for k in ks:
                yield (
                    compiled_graph.generate_stim_circuit(k, noise_model_factory(p)), k, p
                )

    except that the order in which the results are returned is not guaranteed.

    Args:
        compiled_graph: computation to export to `stim.Circuit` instances.
        ks: values of `k` to consider.
        ps: values of `p`, the noise strength, to consider.
        noise_model_factory: a callable that builds a noise model from an input
            strength `p`.
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
        max_workers: The maximum number of processes that can be used to
            execute the given calls. If None or not given then as many
            worker processes will be created as the machine has processors.

    Yields:
        a tuple containing the resulting circuit, the value of `k` that
        corresponds to the returned circuit and the value of `p` that corresponds
        to the returned circuit.
    """
    with ProcessPoolExecutor(max_workers) as executor:
        yield from executor.map(
            functools.partial(
                _parallel_func,
                compiled_graph=compiled_graph,
                noise_model_factory=noise_model_factory,
                manhattan_radius=manhattan_radius,
            ),
            itertools.product(ks, ps),
        )


def generate_sinter_tasks(
    compiled_graph: CompiledGraph,
    ks: Iterable[int],
    ps: Iterable[float],
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
    max_workers: int | None = None,
) -> Iterator[sinter.Task]:
    """Generate `sinter.Task` instances from the provided parameters.

    This function generate the `sinter.Task` instances for all the combinations
    of the given `ks` and `ps` with a noise model that depends on `p` and
    computed with `noise_model_factory`.

    Args:
        compiled_graph: computation to export to `stim.Circuit` instances.
        ks: values of `k` to consider.
        ps: values of `p`, the noise strength, to consider.
        noise_model_factory: a callable that builds a noise model from an input
            strength `p`.
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
        max_workers: The maximum number of processes that can be used to
            execute the given calls. If None or not given then as many
            worker processes will be created as the machine has processors.

    Yields:
        tasks to be collected by a call to `sinter.collect`.
    """
    yield from (
        sinter.Task(
            circuit=circuit,
            json_metadata={"d": 2 * k + 1, "r": 2 * k + 1, "p": p},
        )
        for circuit, k, p in generate_stim_circuits_with_detectors(
            compiled_graph, ks, ps, noise_model_factory, manhattan_radius, max_workers
        )
    )
