from unittest.mock import patch

import numpy
import pytest
import stim

from tqec.compile import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.exact import _deterministic_checks, _strip_annotations
from tqec.compile.detectors.open_boundary import build_open_boundary_analysis_circuit
from tqec.compile.detectors.space import GF2Basis
from tqec.computation.block_graph import BlockGraph
from tqec.gallery import cnot, memory, move_rotation, three_cnots
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


@pytest.mark.parametrize("factory", [memory, cnot, move_rotation, three_cnots])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
@pytest.mark.parametrize("convention", [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION])
def test_complete_logical_semantics_are_independent_of_emission(factory, basis, convention) -> None:
    graph = factory(basis)
    selected = graph.find_correlation_surfaces()[:1]
    spaces = []
    for observables in [None, selected, "auto"]:
        tree = compile_block_graph(graph, convention, observables).to_layer_tree()
        with patch.object(BlockGraph, "find_correlation_surfaces", side_effect=AssertionError):
            circuit = tree.generate_circuit(
                1, database_path=None, manhattan_radius=0, detector_backend="exact"
            )
        analysis = build_open_boundary_analysis_circuit(tree, 1, circuit)
        supports = analysis.logical_supports
        if observables == "auto":
            emitted = _strip_annotations(circuit)[2]
            assert tuple(emitted[i] for i in range(len(supports))) == supports
        checks, _ = _deterministic_checks(circuit)
        space = GF2Basis(c.measurements for c in _strip_annotations(circuit)[1])
        assert space.rank == len(checks) - len(supports)
        assert tree._logical_observables is not None
        assert circuit.num_observables == (
            0
            if observables is None
            else len(selected if observables != "auto" else tree._logical_observables)
        )
        assert not numpy.asarray(circuit.compile_detector_sampler().sample(16)).any()
        spaces.append(space)
    assert all(space.rank == spaces[0].rank for space in spaces)
    assert all(spaces[0].contains(row) for space in spaces for row in space.rows)


def test_discovery_runs_once_after_normalization() -> None:
    graph = cnot(Basis.Z).shift_by(dz=3)
    calls = []
    original = BlockGraph.find_correlation_surfaces

    def discover(normalized, *args, **kwargs):
        calls.append(normalized)
        return original(normalized, *args, **kwargs)

    with patch.object(BlockGraph, "find_correlation_surfaces", discover):
        compiled = compile_block_graph(graph, observables=None)
        compiled.generate_stim_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert len(calls) == 1
    assert min(c.position.z for c in calls[0].cubes) == 0


def test_incomplete_external_generators_disable_completion() -> None:
    tree = compile_block_graph(memory()).to_layer_tree()
    assert tree._logical_surfaces is not None
    tree._logical_surfaces *= 2
    with pytest.warns(UserWarning, match="completion disabled"):
        circuit = tree.generate_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert circuit.num_detectors == 0


@pytest.mark.parametrize("k,local_rank,exact_rank", [(1, 109, 110), (2, 512, 514)])
def test_issue_1000_completes_syndrome_rank(k, local_rank, exact_rank) -> None:
    graph = BlockGraph()
    positions = [
        Position3D(0, 0, 0),
        Position3D(0, 1, 0),
        Position3D(-1, 0, 0),
        Position3D(0, 1, 1),
    ]
    for position, kind in zip(positions, ["XXZ", "XZZ", "ZXZ", "XZZ"]):
        graph.add_cube(position, kind)
    for a, b in [(0, 1), (0, 2), (1, 3)]:
        graph.add_pipe(positions[a], positions[b])
    tree = compile_block_graph(graph, FIXED_BOUNDARY_CONVENTION).to_layer_tree()
    local = tree.generate_circuit(k, database_path=None, detector_database=DetectorDatabase())
    exact = tree.generate_circuit(k, database_path=None, detector_backend="exact")
    local_space = GF2Basis(c.measurements for c in _strip_annotations(local)[1])
    exact_space = GF2Basis(c.measurements for c in _strip_annotations(exact)[1])
    checks, _ = _deterministic_checks(exact)
    assert local_space.rank == local_rank
    assert tree._logical_observables is not None
    assert exact_space.rank == len(checks) - len(tree._logical_observables) == exact_rank
    assert all(exact_space.contains(row) for row in local_space.rows)


def test_issue_1062_removes_globally_nondeterministic_local_candidates() -> None:
    graph = BlockGraph()
    for z in (0, 1):
        positions = [Position3D(0, 1, z), Position3D(1, 1, z), Position3D(1, 0, z)]
        for position, kind in zip(positions, ["XZX", "ZZX", "ZXX"]):
            graph.add_cube(position, kind)
        graph.add_pipe(positions[0], positions[1])
        graph.add_pipe(positions[1], positions[2])
    tree = compile_block_graph(graph, observables=None).to_layer_tree()
    local = tree.generate_circuit(1, database_path=None, detector_database=DetectorDatabase())
    checks, _ = _deterministic_checks(local)
    deterministic = GF2Basis(checks)
    bad = [
        c.measurements
        for c in _strip_annotations(local)[1]
        if not deterministic.contains(c.measurements)
    ]
    assert bad
    exact = tree.generate_circuit(1, database_path=None, detector_backend="exact")
    kept = {c.measurements for c in _strip_annotations(exact)[1]}
    assert not kept.intersection(bad)
    assert all(deterministic.contains(row) for row in kept)
    exact.detector_error_model(allow_gauge_detectors=False, decompose_errors=False)
    assert not numpy.asarray(exact.compile_detector_sampler().sample(32)).any()


@pytest.mark.parametrize("observables", [None, "auto"])
def test_unavailable_discovery_allows_filtering_without_completion(observables) -> None:
    with patch.object(BlockGraph, "find_correlation_surfaces", side_effect=NotImplementedError):
        with pytest.warns(UserWarning, match="Full logical semantics unavailable"):
            tree = compile_block_graph(memory(), observables=observables).to_layer_tree()
    circuit = tree.generate_circuit(
        1, manhattan_radius=0, database_path=None, detector_backend="exact"
    )
    assert circuit.num_detectors == 0
    assert tree._logical_observables is None


def test_single_cube_external_stabilizer_has_one_boundary_qubit() -> None:
    graph = memory(Basis.Z)
    assert graph.find_correlation_surfaces()[0].external_stabilizer_on_graph(graph) == "Z"


@pytest.mark.parametrize("factory", [memory, cnot])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
def test_successful_exact_backend_analyzes_flows_once(factory, basis) -> None:
    tree = compile_block_graph(factory(basis)).to_layer_tree()
    original = stim.Circuit.flow_generators
    calls = []

    def analyze(circuit):
        calls.append(circuit)
        return original(circuit)

    with patch.object(stim.Circuit, "flow_generators", analyze):
        circuit = tree.generate_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert len(calls) == 1
    assert calls[0].num_qubits > circuit.num_qubits
    assert circuit.num_detectors > 0
    local = tree.generate_circuit(1, manhattan_radius=0, database_path=None)
    assert _strip_annotations(circuit)[0] == _strip_annotations(local)[0]
