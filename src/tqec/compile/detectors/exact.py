"""Global exact detector validation and completion using Stim flows."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import stim

from tqec.compile.detectors.space import GF2Basis


@dataclass(frozen=True)
class _DetectorCandidate:
    measurements: int
    coordinates: tuple[float, ...]


def _instruction_measurement_count(instruction: stim.CircuitInstruction) -> int:
    circuit = stim.Circuit()
    circuit.append(instruction)
    return circuit.num_measurements


def _measurement_bits(targets: list[stim.GateTarget], seen: int) -> int:
    bits = 0
    for target in targets:
        if target.is_measurement_record_target:
            bits ^= 1 << (seen + target.value)
    return bits


def _strip_annotations(
    circuit: stim.Circuit,
) -> tuple[stim.Circuit, list[_DetectorCandidate], dict[int, int]]:
    stripped = stim.Circuit()
    candidates: list[_DetectorCandidate] = []
    observables: dict[int, int] = defaultdict(int)
    seen = 0
    for instruction in circuit.flattened():
        assert isinstance(instruction, stim.CircuitInstruction)
        if instruction.name == "DETECTOR":
            candidates.append(
                _DetectorCandidate(
                    _measurement_bits(instruction.targets_copy(), seen),
                    tuple(instruction.gate_args_copy()),
                )
            )
        else:
            stripped.append(instruction)
            if instruction.name == "OBSERVABLE_INCLUDE":
                observable = int(instruction.gate_args_copy()[0])
                observables[observable] ^= _measurement_bits(instruction.targets_copy(), seen)
        seen += _instruction_measurement_count(instruction)
    return stripped, candidates, observables


def _zero_valued_relation_basis(circuit: stim.Circuit) -> tuple[int, ...]:
    """Return a basis of deterministic measurement parities whose value is zero."""
    rows: list[tuple[int, bool]] = []
    for flow in circuit.flow_generators():
        input_pauli = flow.input_copy()
        output_pauli = flow.output_copy()
        if input_pauli.weight or output_pauli.weight:
            continue
        bits = 0
        for measurement in flow.measurements_copy():
            bits ^= 1 << measurement
        if bits:
            rows.append((bits, input_pauli.sign != output_pauli.sign))

    negative_reference = next((bits for bits, negative in rows if negative), None)
    zero_rows = []
    for bits, negative in rows:
        zero_bits = bits
        if negative:
            assert negative_reference is not None
            zero_bits ^= negative_reference
        if zero_bits:
            zero_rows.append(zero_bits)
    return GF2Basis(zero_rows).rows


def annotate_detectors_exactly(circuit: stim.Circuit, *, complete: bool = True) -> stim.Circuit:
    """Validate local detectors and complete known deterministic relations.

    Existing detectors are treated as preferred candidates. Candidates outside
    the exact deterministic relation space are removed. When ``complete`` is
    true, missing directions are appended modulo the supplied observables and
    the validated local candidates. This quotient relies on those annotations
    to encode the circuit's logical semantics.

    This is a global reference implementation: it flattens repeat blocks and is
    intended to establish correctness before a compositional implementation is
    introduced.
    """
    stripped, candidates, observables = _strip_annotations(circuit.without_noise())
    relations = _zero_valued_relation_basis(stripped)
    relation_space = GF2Basis(relations)

    selected: list[_DetectorCandidate] = []
    selected_rows: set[int] = set()
    covered_space = GF2Basis(
        observable
        for observable in observables.values()
        if observable and relation_space.contains(observable)
    )
    for candidate in candidates:
        row = candidate.measurements
        if row and row not in selected_rows and relation_space.contains(row):
            selected.append(candidate)
            selected_rows.add(row)
            covered_space.add(row)

    # Complete R modulo the observable and trusted local-detector directions.
    if complete:
        for relation in sorted(relations, key=lambda row: (row.bit_count(), row)):
            remainder = covered_space.reduce(relation)
            if remainder:
                covered_space.add(remainder)
                selected.append(_DetectorCandidate(remainder, ()))

    measurement_count = stripped.num_measurements
    for candidate in selected:
        targets = [
            stim.target_rec(index - measurement_count)
            for index in range(measurement_count)
            if candidate.measurements >> index & 1
        ]
        stripped.append("DETECTOR", targets, candidate.coordinates)

    stripped.detector_error_model(allow_gauge_detectors=False, decompose_errors=False)
    return stripped
