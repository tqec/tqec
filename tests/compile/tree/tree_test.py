from unittest.mock import patch

import numpy
import pytest
import stim

from tqec.compile import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.detectors.exact import _deterministic_checks, _strip_annotations
from tqec.compile.detectors.open_boundary import build_open_boundary_analysis_circuit
from tqec.compile.detectors.space import GF2Basis
from tqec.computation.block_graph import BlockGraph
from tqec.gallery import cnot, memory, move_rotation, three_cnots
from tqec.utils.enums import Basis


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


def test_incomplete_external_generators_disable_completion() -> None:
    tree = compile_block_graph(memory()).to_layer_tree()
    assert tree._logical_surfaces is not None
    tree._logical_surfaces *= 2
    with pytest.warns(UserWarning, match="completion disabled"):
        circuit = tree.generate_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert circuit.num_detectors == 0


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
