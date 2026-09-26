"""Global exact detector validation and completion using Stim flows."""

from __future__ import annotations

import warnings
from collections import defaultdict
from dataclasses import dataclass

import stim

from tqec.compile.detectors.space import GF2Basis, nullspace, xor_rows


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


def _deterministic_checks(circuit: stim.Circuit) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Extract independent measurement checks and their expected parity, without losing signs."""
    basis = GF2Basis()
    signs = []
    for flow in circuit.flow_generators():
        inp, out = flow.input_copy(), flow.output_copy()
        if inp.weight or out.weight:
            continue
        row = 0
        for measurement in flow.measurements_copy():
            row ^= 1 << measurement
        if basis.add(row):
            signs.append(int(inp.sign != out.sign))
    return basis.generators, tuple(signs)


def _syndrome_space(
    circuit: stim.Circuit,
    checks: tuple[int, ...],
    signs: tuple[int, ...],
    perturbations: list[stim.Circuit],
    logical_supports: list[int],
) -> GF2Basis:
    """Compute ker(F^T) C and verify the bound logical generators respond as the dual basis."""
    check_basis = GF2Basis(checks)
    logical_coefficients = [check_basis.decompose(row) for row in logical_supports]
    if any(row is None for row in logical_coefficients):
        raise ValueError("A logical correlation is not deterministic.")
    if len(perturbations) != len(logical_supports):
        raise ValueError("Incomplete logical perturbations.")
    responses = []
    for j, perturbed in enumerate(perturbations):
        if perturbed.num_measurements != circuit.num_measurements:
            raise ValueError("A logical perturbation changed the measurement count.")
        rows, perturbed_signs = _deterministic_checks(perturbed)
        basis = GF2Basis(rows)
        response = 0
        for i, (check, sign) in enumerate(zip(checks, signs)):
            coefficients = basis.decompose(check)
            if coefficients is None:
                raise ValueError("A logical perturbation made a check nondeterministic.")
            response |= (xor_rows(coefficients, perturbed_signs) ^ sign) << i
        for i, coefficients in enumerate(logical_coefficients):
            assert coefficients is not None
            if (coefficients & response).bit_count() % 2 != (i == j):
                raise ValueError("Physical logical response disagrees with external stabilizers.")
        responses.append(response)
    if GF2Basis(responses).rank != len(logical_supports):
        raise ValueError("Incomplete logical response rank.")
    return GF2Basis(xor_rows(x, checks) for x in nullspace(responses, len(checks)))


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
    logical_perturbations: list[stim.Circuit] | None = None,
    logical_supports: list[int] | None = None,
) -> stim.Circuit:
    """Filter local candidates and complete only with verified logical semantics.

    Stim determines signed deterministic checks C. Independent physical logical
    Paulis determine their response F; valid syndrome checks span ker(F^T) C.
    Missing or inconsistent semantics disable completion and only nondeterministic
    local candidates are removed. Emitted observables never define this space.
    """
    stripped, candidates, _ = _strip_annotations(circuit.without_noise())
    checks, signs = _deterministic_checks(stripped)
    relation_space = GF2Basis(checks)
    syndrome_space = None
    if complete and logical_perturbations is not None and logical_supports is not None:
        try:
            syndrome_space = _syndrome_space(
                stripped, checks, signs, logical_perturbations, logical_supports
            )
        except ValueError as error:
            warnings.warn(f"Exact detector completion disabled: {error}", stacklevel=2)
    allowed = syndrome_space if syndrome_space is not None else relation_space
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
    assert all(relation_space.contains(candidate.measurements) for candidate in selected)
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
