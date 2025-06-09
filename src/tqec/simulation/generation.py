from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import sinter
import stim

from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.graph import TopologicalComputationGraph
from tqec.utils.noise_model import NoiseModel
from tqec.utils.paths import DEFAULT_DETECTOR_DATABASE_PATH


def generate_stim_circuits_with_detectors(
    compiled_graph: TopologicalComputationGraph,
    ks: Iterable[int],
    ps: Iterable[float],
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
    detector_database: DetectorDatabase | None = None,
    database_path: str | Path = DEFAULT_DETECTOR_DATABASE_PATH,
    do_not_use_database: bool = False,
    only_use_database: bool = False,
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
        detector_database: an instance to retrieve from / store in detectors
            that are computed as part of the circuit generation. If not given,
            the detectors are retrieved from/stored in the provided
            ``database_path``.
        database_path: specify where to save to after the calculation.
            This defaults to :class:`.DEFAULT_DETECTOR_DATABASE_PATH` if
            not specified. If ``detector_database`` is not passed in, the code attempts to
            retrieve the database from this location. The user may pass in the path
            either in str format, or as a Path instance.
        do_not_use_database: if ``True``, even the default database will not be used.
        only_use_database: if ``True``, only detectors from the database
            will be used. An error will be raised if a situation that is not
            registered in the database is encountered.

    Yields:
        a tuple containing the resulting circuit, the value of `k` that
        corresponds to the returned circuit and the value of `p` that corresponds
        to the returned circuit.

    """
    noise_models = {p: noise_model_factory(p) for p in ps}
    circuits = {
        k: compiled_graph.generate_stim_circuit(
            k,
            manhattan_radius=manhattan_radius,
            detector_database=detector_database,
            database_path=database_path,
            do_not_use_database=do_not_use_database,
            only_use_database=only_use_database,
        )
        for k in ks
    }
    yield from (
        (nm.noisy_circuit(circuit), k, p)
        for k, circuit in circuits.items()
        for p, nm in noise_models.items()
    )


def generate_sinter_tasks(
    compiled_graph: TopologicalComputationGraph,
    ks: Iterable[int],
    ps: Iterable[float],
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
    detector_database: DetectorDatabase | None = None,
    database_path: str | Path = DEFAULT_DETECTOR_DATABASE_PATH,
    do_not_use_database: bool = False,
    only_use_database: bool = False,
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
        detector_database: an instance to retrieve from / store in detectors
            that are computed as part of the circuit generation. If not given,
            the detectors are retrieved from/stored in the provided
            ``database_path``.
        database_path: specify where to save to after the calculation.
            This defaults to :data:`.DEFAULT_DETECTOR_DATABASE_PATH` if
            not specified. If ``detector_database`` is not passed in, the code attempts to
            retrieve the database from this location. The user may pass in the path
            either in str format, or as a Path instance.
        do_not_use_database: if ``True``, even the default database will not be used.
        only_use_database: if ``True``, only detectors from the database
            will be used. An error will be raised if a situation that is not
            registered in the database is encountered.

    Yields:
        tasks to be collected by a call to `sinter.collect`.

    """
    yield from (
        sinter.Task(
            circuit=circuit,
            json_metadata={"d": 2 * k + 1, "r": 2 * k + 1, "p": p},
        )
        for circuit, k, p in generate_stim_circuits_with_detectors(
            compiled_graph,
            ks,
            ps,
            noise_model_factory,
            manhattan_radius,
            detector_database,
            database_path=database_path,
            do_not_use_database=do_not_use_database,
            only_use_database=only_use_database,
        )
    )
