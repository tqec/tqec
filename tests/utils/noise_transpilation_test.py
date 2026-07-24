"""Tests for :func:`tqec.transpile_to_si1000_gateset`.

The transpiler must satisfy three properties that ``tqec.processing.simulate`` relies on when it
applies SI1000 noise to a detector-annotated circuit:

1. Gate-set closure: the result only uses the Z-basis interaction gate set that
   ``NoiseModel.si1000`` supports, so ``si1000`` can be applied without raising.
2. Semantic equivalence: the result reproduces the original circuit's measurement statistics
   (verified through Stim flows).
3. Annotation preservation: ``DETECTOR`` / ``OBSERVABLE_INCLUDE`` parities and the
   measurement-record ordering they reference survive the rewrite.
"""

import stim

import tqec
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.gallery.memory import memory
from tqec.utils.enums import Basis
from tqec.utils.noise_model import OP_TYPES, NoiseModel
from tqec.utils.noise_transpilation import transpile_to_si1000_gateset

# Non-Z-basis collapses (and multi-qubit measurements) that ``NoiseModel.si1000`` rejects.
_BANNED_COLLAPSES = frozenset(["RX", "RY", "MX", "MY", "MRX", "MRY", "MXX", "MYY", "MZZ", "MPP"])

# The extended single-qubit Clifford cycle gates that the transpiler can emit.
_EXTENDED_1Q_CLIFFORDS = ("C_NXYZ", "C_XNYZ", "C_XYNZ", "C_NZYX", "C_ZNYX", "C_ZYNX")


def _gate_names(circuit: stim.Circuit) -> set[str]:
    return {inst.name for inst in circuit.flattened()}


def _measurement_outcome_flows(circuit: stim.Circuit) -> list[stim.Flow]:
    """Return the flows describing the circuit's measurement outcomes.

    These are the flow generators whose output Pauli is the identity, i.e. the pure
    input-Pauli-to-measurement-parity relations. Two circuits inducing the same such flows (with
    the same number of measurements) produce identical measurement statistics -- the transpiler is
    free to change the residual Pauli frame left on qubits, which is exactly the non-identity-output
    flows that this filter drops.
    """
    return [f for f in circuit.flow_generators() if len(f.output_copy()) == 0]


def _detector_and_observable_flows(circuit: stim.Circuit) -> list[stim.Flow]:
    """Reconstruct every DETECTOR / OBSERVABLE_INCLUDE as an explicit ``1 -> parity`` flow.

    The measurement records are converted to absolute indices, so ``has_flow`` on another circuit
    checks both that the parity is deterministic there and that it references the same measurements.
    """
    flows: list[stim.Flow] = []
    running = 0
    for inst in circuit.flattened():
        assert not isinstance(inst, stim.CircuitRepeatBlock)
        if inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            records = [
                running + t.value for t in inst.targets_copy() if t.is_measurement_record_target
            ]
            flows.append(stim.Flow(measurements=records))
        elif stim.gate_data(inst.name).produces_measurements:
            running += sum(1 for t in inst.targets_copy() if not t.is_combiner)
    return flows


def _assert_measurement_equivalent(original: stim.Circuit, transpiled: stim.Circuit) -> None:
    assert original.num_measurements == transpiled.num_measurements
    for flow in _measurement_outcome_flows(original):
        assert transpiled.has_flow(flow), f"transpiled circuit lost flow {flow}"
    for flow in _measurement_outcome_flows(transpiled):
        assert original.has_flow(flow), f"transpiled circuit invented flow {flow}"


def _handwritten_y_basis_circuit() -> stim.Circuit:
    """Return a circuit with RY/MY (and RX/MX), Cliffords and entangling gates.

    The measured qubits are entangled, so the individual measurements are not deterministic; this
    circuit is used to check gate-set closure and measurement-statistics equivalence, not detector
    determinism (see :func:`_deterministic_y_basis_circuit` for that).
    """
    return stim.Circuit("""
        QUBIT_COORDS(0, 0) 0
        QUBIT_COORDS(1, 0) 1
        QUBIT_COORDS(2, 0) 2
        RY 0
        RX 1
        R 2
        TICK
        H 1
        TICK
        CX 1 0
        TICK
        CZ 0 2
        TICK
        S 0
        TICK
        MY 0
        MX 1
        M 2
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)


def _deterministic_y_basis_circuit() -> stim.Circuit:
    """Return a circuit with deterministic RY/MY (and RX/MX) detectors and an observable."""
    return stim.Circuit("""
        QUBIT_COORDS(0, 0) 0
        QUBIT_COORDS(1, 0) 1
        QUBIT_COORDS(2, 0) 2
        RY 0
        RX 1
        R 2
        TICK
        MY 0
        MX 1
        M 2
        DETECTOR(0, 0) rec[-3]
        DETECTOR(1, 0) rec[-2]
        DETECTOR(2, 0) rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-3]
    """)


def _compiled_memory_circuit(basis: Basis) -> stim.Circuit:
    graph = memory(basis)
    compiled = compile_block_graph(graph, FIXED_BULK_CONVENTION, graph.find_correlation_surfaces())
    return compiled.to_layer_tree().generate_circuit(1)


def test_extended_cliffords_registered_in_op_types() -> None:
    for gate in _EXTENDED_1Q_CLIFFORDS:
        assert OP_TYPES.get(gate) == "C1", gate


def test_public_import_path() -> None:
    assert tqec.transpile_to_si1000_gateset is transpile_to_si1000_gateset


def test_gate_set_closure_on_handwritten_y_basis() -> None:
    original = _handwritten_y_basis_circuit()
    assert _gate_names(original) & _BANNED_COLLAPSES, "test input must exercise non-Z collapses"

    transpiled = transpile_to_si1000_gateset(original)

    assert not (_gate_names(transpiled) & _BANNED_COLLAPSES)
    # The whole point: si1000 raises on the original but not on the transpiled circuit.
    NoiseModel.si1000(0.001).noisy_circuit(transpiled)


def test_semantic_equivalence_on_handwritten_y_basis() -> None:
    original = _handwritten_y_basis_circuit()
    transpiled = transpile_to_si1000_gateset(original)
    _assert_measurement_equivalent(original, transpiled)


def test_annotations_preserved_on_handwritten_y_basis() -> None:
    original = _deterministic_y_basis_circuit()
    transpiled = transpile_to_si1000_gateset(original)

    assert transpiled.num_detectors == original.num_detectors
    assert transpiled.num_observables == original.num_observables

    original_flows = _detector_and_observable_flows(original)
    # Sanity: the hand-written detectors / observable really are deterministic on the original.
    for flow in original_flows:
        assert original.has_flow(flow)
    # Each detector / observable parity must remain a deterministic parity over the same
    # measurements in the transpiled circuit, and vice versa.
    for flow in original_flows:
        assert transpiled.has_flow(flow)
    for flow in _detector_and_observable_flows(transpiled):
        assert original.has_flow(flow)


def test_detector_measurement_record_ordering_preserved() -> None:
    """A detector's referenced measurements must still be referenced after transpilation."""
    # Qubit 0 is prepared and measured twice in the Y basis with no intervening operation, so the
    # two Y measurements are deterministically equal: DETECTOR rec[-1] xor rec[-2] must be 0.
    original = stim.Circuit("""
        RY 0
        TICK
        MY 0
        TICK
        MY 0
        DETECTOR rec[-1] rec[-2]
    """)
    transpiled = transpile_to_si1000_gateset(original)

    assert transpiled.num_measurements == 2
    assert transpiled.num_detectors == 1
    # detector_error_model() raises unless every detector is deterministically false, so this
    # asserts the detector is both deterministic and satisfied in each circuit.
    original.detector_error_model()
    transpiled.detector_error_model()
    # And the parity references the same two measurements.
    (flow,) = _detector_and_observable_flows(original)
    assert transpiled.has_flow(flow)


def test_transpiled_circuit_is_idempotent_under_si1000() -> None:
    """A circuit already in the target gate set is unaffected on the properties that matter."""
    original = _handwritten_y_basis_circuit()
    once = transpile_to_si1000_gateset(original)
    twice = transpile_to_si1000_gateset(once)
    assert not (_gate_names(twice) & _BANNED_COLLAPSES)
    _assert_measurement_equivalent(once, twice)


def test_compiled_memory_x_basis_end_to_end() -> None:
    original = _compiled_memory_circuit(Basis.X)
    assert _gate_names(original) & _BANNED_COLLAPSES, "compiled X memory must contain X collapses"

    transpiled = transpile_to_si1000_gateset(original)

    # Gate-set closure.
    assert not (_gate_names(transpiled) & _BANNED_COLLAPSES)
    # si1000 applies and yields a well-formed detector error model.
    noisy = NoiseModel.si1000(0.001).noisy_circuit(transpiled)
    noisy.detector_error_model(decompose_errors=True)

    # Counts, measurement statistics and annotations are all preserved.
    assert transpiled.num_measurements == original.num_measurements
    assert transpiled.num_detectors == original.num_detectors
    assert transpiled.num_observables == original.num_observables
    _assert_measurement_equivalent(original, transpiled)
    for flow in _detector_and_observable_flows(original):
        assert transpiled.has_flow(flow)
    # Detectors remain deterministically false (detector_error_model() raises otherwise).
    transpiled.detector_error_model()
