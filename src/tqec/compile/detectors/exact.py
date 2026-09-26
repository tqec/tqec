"""Global exact detector validation and completion using Stim flows."""

from __future__ import annotations

import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import stim

from tqec.compile.detectors.space import GF2Basis, xor_rows

if TYPE_CHECKING:
    from tqec.compile.detectors.open_boundary import _OpenBoundaryAnalysis


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


def _flow_vector(flow: stim.Flow, num_qubits: int, num_measurements: int) -> int:
    """Encode measurement support followed by input/output symplectic coordinates."""
    row = 0
    for measurement in flow.measurements_copy():
        row ^= 1 << (measurement % num_measurements)
    for side, pauli in enumerate((flow.input_copy(), flow.output_copy())):
        for qubit in range(len(pauli)):
            value = pauli[qubit]
            shift = num_measurements + side * 2 * num_qubits + qubit
            if value in (1, 2):
                row ^= 1 << shift
            if value in (2, 3):
                row ^= 1 << (shift + num_qubits)
    return row


def _multiply_flows(left: stim.Flow, right: stim.Flow) -> stim.Flow:
    """Multiply flow relations, letting Stim Pauli algebra retain their phases.

    Use PauliString products instead of Flow.__mul__ for Stim 1.14 compatibility.
    Input and output may both anticommute: their imaginary phases cancel.
    """
    inp = left.input_copy() * right.input_copy()
    out = left.output_copy() * right.output_copy()
    out.sign /= inp.sign
    inp.sign = 1
    if out.sign not in (1, -1):
        raise ValueError("Incompatible flow phases.")
    return stim.Flow(
        input=inp,
        output=out,
        measurements=sorted(set(left.measurements_copy()) ^ set(right.measurements_copy())),
    )


def _flow_product(coefficients: int, flows: list[stim.Flow]) -> stim.Flow:
    result = stim.Flow()
    for i, flow in enumerate(flows):
        if coefficients >> i & 1:
            result = _multiply_flows(result, flow)
    return result


def _measurement_checks(
    flows: list[stim.Flow], num_qubits: int, num_measurements: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Eliminate *all* input/output Pauli columns, retaining signed measurement relations."""
    pivots: dict[int, tuple[int, stim.Flow]] = {}
    checks = GF2Basis()
    signs = []
    for original_flow in flows:
        flow = original_flow
        boundary = _flow_vector(flow, num_qubits, num_measurements) >> num_measurements
        while boundary:
            pivot = boundary.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = boundary, flow
                break
            other_boundary, other_flow = pivots[pivot]
            boundary ^= other_boundary
            flow = _multiply_flows(flow, other_flow)
        else:
            row = _flow_vector(flow, num_qubits, num_measurements)
            sign = int(flow.input_copy().sign != flow.output_copy().sign)
            if checks.add(row):
                signs.append(sign)
    return checks.generators, tuple(signs)


def _deterministic_checks(circuit: stim.Circuit) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Extract signed checks; used for conservative closed-circuit filtering only."""
    return _measurement_checks(
        circuit.flow_generators(), circuit.num_qubits, circuit.num_measurements
    )


def _syndrome_space(analysis: _OpenBoundaryAnalysis) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Analyze once, validate external correlations, and eliminate open boundary Paulis."""
    circuit = analysis.circuit
    if len(analysis.measurement_map) != circuit.num_measurements:
        raise ValueError("Incomplete analysis measurement mapping.")
    flows = circuit.flow_generators()
    algebra = GF2Basis()
    generators = []
    for flow in flows:
        if algebra.add(_flow_vector(flow, circuit.num_qubits, circuit.num_measurements)):
            generators.append(flow)  # noqa: PERF401
    boundary = GF2Basis()
    for expected in analysis.logical_flows:
        row = _flow_vector(expected, circuit.num_qubits, circuit.num_measurements)
        if not boundary.add(row >> circuit.num_measurements):
            raise ValueError("Open ports do not distinguish every logical correlation.")
        coefficients = algebra.decompose(row)
        if coefficients is None:
            raise ValueError("External stabilizer is absent from the open-circuit flow space.")
        actual = _flow_product(coefficients, generators)
        if (actual.input_copy().sign != actual.output_copy().sign) != (
            expected.input_copy().sign != expected.output_copy().sign
        ):
            raise ValueError("External stabilizer flow has the wrong sign.")
    rows, signs = _measurement_checks(flows, circuit.num_qubits, circuit.num_measurements)
    checks = GF2Basis()
    mapped_signs = []
    for row, sign in zip(rows, signs):
        mapped = xor_rows(row, analysis.measurement_map)
        coefficients = checks.decompose(mapped)
        if coefficients is None:
            checks.add(mapped)
            mapped_signs.append(sign)
        elif xor_rows(coefficients, mapped_signs) != sign:
            raise ValueError("Analysis measurement mapping has inconsistent signs.")
    return checks.generators, tuple(mapped_signs)


def _check_costs(circuit: stim.Circuit):
    """Rank completion choices by weight, temporal extent, then spatial extent."""
    times: list[int] = []
    positions: list[list[float]] = []
    coordinates = circuit.get_final_qubit_coordinates()
    tick = 0
    for instruction in circuit:
        assert isinstance(instruction, stim.CircuitInstruction)
        tick += instruction.name == "TICK"
        count = _instruction_measurement_count(instruction)
        times.extend([tick] * count)
        targets = instruction.targets_copy()
        if len(targets) == count:
            positions.extend(coordinates.get(target.value, [])[:2] for target in targets)
        else:
            positions.extend([] for _ in range(count))

    def cost(row: int) -> tuple[int, int, float, int]:
        indices = []
        remaining = row
        while remaining:
            bit = remaining & -remaining
            indices.append(bit.bit_length() - 1)
            remaining ^= bit
        spatial_span = sum(
            max(values) - min(values)
            for axis in range(2)
            if (values := [positions[i][axis] for i in indices if len(positions[i]) > axis])
        )
        return (len(indices), times[indices[-1]] - times[indices[0]], spatial_span, row)

    return cost


def annotate_detectors_exactly(
    circuit: stim.Circuit,
    *,
    complete: bool = True,
    analysis: _OpenBoundaryAnalysis | None = None,
) -> stim.Circuit:
    """Filter and complete using identity-boundary flows of an open analysis circuit.

    Emitted observables never define the syndrome space. Missing or inconsistent
    open-boundary semantics disable completion; the closed circuit then only
    filters nondeterministic local candidates. Both analyses preserve signs.
    """
    stripped, candidates, _ = _strip_annotations(circuit.without_noise())
    syndrome_space = None
    if complete and analysis is not None:
        try:
            if analysis.circuit.num_measurements != stripped.num_measurements:
                raise ValueError("Analysis changed the measurement record count.")
            checks, _ = _syndrome_space(analysis)
            if any(row >> stripped.num_measurements for row in checks):
                raise ValueError("Analysis mapped outside the original measurement records.")
            syndrome_space = GF2Basis(checks)
        except ValueError as error:
            warnings.warn(f"Exact detector completion disabled: {error}", stacklevel=2)
    if syndrome_space is None:
        checks, _ = _deterministic_checks(stripped)
        allowed = GF2Basis(checks)
    else:
        allowed = syndrome_space
    selected = []
    selected_rows: set[int] = set()
    covered = GF2Basis()
    for candidate in candidates:
        row = candidate.measurements
        if row and row not in selected_rows and allowed.contains(row):
            selected.append(candidate)
            selected_rows.add(row)
            covered.add(row)
    if syndrome_space is not None:
        cost = _check_costs(stripped)
        for row in sorted(syndrome_space.rows, key=cost):
            # Reducing by preferred local checks usually produces a much smaller check.
            remainder = covered.reduce(row)
            if remainder:
                best = min((row, remainder), key=cost)
                covered.add(best)
                selected.append(_DetectorCandidate(best, ()))
        assert covered.rank == syndrome_space.rank
    assert all(allowed.contains(candidate.measurements) for candidate in selected)
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
