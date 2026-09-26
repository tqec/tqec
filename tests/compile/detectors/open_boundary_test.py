from collections import Counter

import pytest
import stim

from tqec.compile import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.detectors.exact import _flow_vector, _syndrome_space
from tqec.compile.detectors.open_boundary import build_open_boundary_analysis_circuit
from tqec.compile.detectors.space import GF2Basis
from tqec.gallery import cnot, memory
from tqec.utils.enums import Basis


@pytest.mark.parametrize("convention", [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
def test_memory_keeps_both_logical_paulis_open(convention, basis) -> None:
    tree = compile_block_graph(memory(basis), convention).to_layer_tree()
    closed = tree.generate_circuit(1, database_path=None, manhattan_radius=0)
    analysis = build_open_boundary_analysis_circuit(tree, 1, closed)
    opened = analysis.circuit
    assert opened.num_measurements == closed.num_measurements
    assert opened.num_qubits == closed.num_qubits + 2
    # Crucially, neither the conjugate operator nor its stabilizer constraints
    # may disappear when opening a memory prepared/read out in one fixed basis.
    boundary = GF2Basis(
        _flow_vector(f, opened.num_qubits, opened.num_measurements) >> opened.num_measurements
        for f in opened.flow_generators()
    )
    for pauli in "XZ":
        inp, out = stim.PauliString(opened.num_qubits), stim.PauliString(opened.num_qubits)
        inp[closed.num_qubits] = out[closed.num_qubits + 1] = pauli
        expected = _flow_vector(stim.Flow(input=inp, output=out), opened.num_qubits, 0)
        assert boundary.contains(expected)
    # Z-memory's Z flow (and X-memory's X flow) needs no intermediate correction.
    logical = analysis.logical_flows[0]
    assert logical.input_copy().weight == logical.output_copy().weight == 1
    assert logical.measurements_copy() == []
    assert opened.has_flow(logical)
    assert len(_syndrome_space(analysis)[0]) == 24


@pytest.mark.parametrize("convention", [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
def test_cnot_has_full_quantum_boundary_flows(convention, basis) -> None:
    tree = compile_block_graph(cnot(basis), convention).to_layer_tree()
    closed = tree.generate_circuit(1, database_path=None, manhattan_radius=0)
    analysis = build_open_boundary_analysis_circuit(tree, 1, closed)
    opened = analysis.circuit
    n = closed.num_qubits
    assert opened.num_qubits == n + 4
    boundary = GF2Basis(
        _flow_vector(f, opened.num_qubits, opened.num_measurements) >> opened.num_measurements
        for f in opened.flow_generators()
    )
    # Ports follow gallery leaf order: input control, output control,
    # input target, output target. Check the full Clifford relation, including
    # the conjugate basis not requested by the closed graph's observable choice.
    for in_terms, out_terms in [
        ([(n, "X")], [(n + 1, "X"), (n + 3, "X")]),
        ([(n + 2, "X")], [(n + 3, "X")]),
        ([(n, "Z")], [(n + 1, "Z")]),
        ([(n + 2, "Z")], [(n + 1, "Z"), (n + 3, "Z")]),
    ]:
        inp, out = stim.PauliString(opened.num_qubits), stim.PauliString(opened.num_qubits)
        for q, pauli in in_terms:
            inp[q] = pauli
        for q, pauli in out_terms:
            out[q] = pauli
        assert boundary.contains(
            _flow_vector(stim.Flow(input=inp, output=out), opened.num_qubits, 0)
        )
    assert opened.has_all_flows(analysis.logical_flows)
    # These are compiled directly from external_stabilizer_on_graph plus the
    # shared observable measurement resolver, not inferred from local detectors.
    assert len(analysis.logical_flows) == 2
    assert len(_syndrome_space(analysis)[0]) == 256


@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
def test_readout_map_preserves_signed_syndrome_checks(basis) -> None:
    tree = compile_block_graph(memory(basis)).to_layer_tree()
    closed = tree.generate_circuit(1, database_path=None, manhattan_radius=0)
    analysis = build_open_boundary_analysis_circuit(tree, 1, closed)
    # Every mapped syndrome must be a signed flow of the actual closed circuit.
    checks, signs = _syndrome_space(analysis)
    for row, sign in zip(checks, signs):
        out = stim.PauliString(0)
        out.sign = -1 if sign else 1
        assert closed.has_flow(
            stim.Flow(
                output=out, measurements=[i for i in range(closed.num_measurements) if row >> i & 1]
            )
        )

    # Decoding does not delete any physical reset/readout: only Clifford gates
    # and an output-port reset were added. The pivot readout is a zero dummy.
    def counts(circuit):
        return Counter(
            (instruction.name, target.value)
            for instruction in circuit.flattened()
            if isinstance(instruction, stim.CircuitInstruction)
            and instruction.name in ("R", "RX", "M", "MX")
            for target in instruction.targets_copy()
            if target.value < closed.num_qubits
        )

    assert counts(analysis.circuit) == counts(closed)
    assert len(analysis.measurement_map) == closed.num_measurements
    assert analysis.measurement_map.count(0) == 1
    assert any(row.bit_count() > 1 for row in analysis.measurement_map)
