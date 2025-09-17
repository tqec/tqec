"""Implementation of different noise models for Stim.

Important note:
---------------

This file has been recovered from https://zenodo.org/records/7487893
and is under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode).
It is part of the code from the paper

    Gidney, C. (2022). Data for "Inplace Access to the Surface Code Y Basis".
    https://doi.org/10.5281/zenodo.7487893


Modifications to the original code:

1. Formatting with ruff.
2. Fixing typing issues and adapting a few imports to personal taste.
3. A minor adjustment to the measurement noise rules of ``uniform_depolarizing``
   and ``si1000`` noise models: the depolarizing error on the measured qubits
   after measurement is removed because, in our library, all measurements are
   immediately followed by resets. As a result, the depolarizing error has no
   effect.
4. Remove the ``depolarizing_two_body_measurement_noise`` noise model.
5. Changes to NoiseModel.noisy_circuit to respect TQEC convention with TICKs and
   REPEAT blocks (not before the block, the first instruction in the repeated
   inner block, and after the block).
6. Re-phrase the docstrings and error messages slightly.

"""

from collections import Counter, defaultdict
from collections.abc import Iterator, Set

import stim

CLIFFORD_1Q = "C1"
CLIFFORD_2Q = "C2"
ANNOTATION = "info"
MPP = "MPP"
MEASURE_RESET_1Q = "MR1"
JUST_MEASURE_1Q = "M1"
JUST_RESET_1Q = "R1"
NOISE = "!?"

OP_TYPES = {
    "I": CLIFFORD_1Q,
    "X": CLIFFORD_1Q,
    "Y": CLIFFORD_1Q,
    "Z": CLIFFORD_1Q,
    "C_XYZ": CLIFFORD_1Q,
    "C_ZYX": CLIFFORD_1Q,
    "H": CLIFFORD_1Q,
    "H_XY": CLIFFORD_1Q,
    "H_XZ": CLIFFORD_1Q,
    "H_YZ": CLIFFORD_1Q,
    "S": CLIFFORD_1Q,
    "SQRT_X": CLIFFORD_1Q,
    "SQRT_X_DAG": CLIFFORD_1Q,
    "SQRT_Y": CLIFFORD_1Q,
    "SQRT_Y_DAG": CLIFFORD_1Q,
    "SQRT_Z": CLIFFORD_1Q,
    "SQRT_Z_DAG": CLIFFORD_1Q,
    "S_DAG": CLIFFORD_1Q,
    "CNOT": CLIFFORD_2Q,
    "CX": CLIFFORD_2Q,
    "CY": CLIFFORD_2Q,
    "CZ": CLIFFORD_2Q,
    "ISWAP": CLIFFORD_2Q,
    "ISWAP_DAG": CLIFFORD_2Q,
    "SQRT_XX": CLIFFORD_2Q,
    "SQRT_XX_DAG": CLIFFORD_2Q,
    "SQRT_YY": CLIFFORD_2Q,
    "SQRT_YY_DAG": CLIFFORD_2Q,
    "SQRT_ZZ": CLIFFORD_2Q,
    "SQRT_ZZ_DAG": CLIFFORD_2Q,
    "SWAP": CLIFFORD_2Q,
    "XCX": CLIFFORD_2Q,
    "XCY": CLIFFORD_2Q,
    "XCZ": CLIFFORD_2Q,
    "YCX": CLIFFORD_2Q,
    "YCY": CLIFFORD_2Q,
    "YCZ": CLIFFORD_2Q,
    "ZCX": CLIFFORD_2Q,
    "ZCY": CLIFFORD_2Q,
    "ZCZ": CLIFFORD_2Q,
    "MPP": MPP,
    "MR": MEASURE_RESET_1Q,
    "MRX": MEASURE_RESET_1Q,
    "MRY": MEASURE_RESET_1Q,
    "MRZ": MEASURE_RESET_1Q,
    "M": JUST_MEASURE_1Q,
    "MX": JUST_MEASURE_1Q,
    "MY": JUST_MEASURE_1Q,
    "MZ": JUST_MEASURE_1Q,
    "R": JUST_RESET_1Q,
    "RX": JUST_RESET_1Q,
    "RY": JUST_RESET_1Q,
    "RZ": JUST_RESET_1Q,
    "DETECTOR": ANNOTATION,
    "OBSERVABLE_INCLUDE": ANNOTATION,
    "QUBIT_COORDS": ANNOTATION,
    "SHIFT_COORDS": ANNOTATION,
    "TICK": ANNOTATION,
    "E": ANNOTATION,
    "DEPOLARIZE1": NOISE,
    "DEPOLARIZE2": NOISE,
    "PAULI_CHANNEL_1": NOISE,
    "PAULI_CHANNEL_2": NOISE,
    "X_ERROR": NOISE,
    "Y_ERROR": NOISE,
    "Z_ERROR": NOISE,
    # Not supported.
    # 'CORRELATED_ERROR': NOISE,
    # 'E': NOISE,
    # 'ELSE_CORRELATED_ERROR',
}
OP_MEASURE_BASES = {
    "M": "Z",
    "MX": "X",
    "MY": "Y",
    "MZ": "Z",
    "MPP": "",
}
COLLAPSING_OPS = {
    op for op, t in OP_TYPES.items() if t in {JUST_RESET_1Q, JUST_MEASURE_1Q, MPP, MEASURE_RESET_1Q}
}


class NoiseRule:
    """Describes how to add noise to an operation."""

    def __init__(self, *, after: dict[str, float], flip_result: float = 0):
        """Describe how to add noise to an operation.

        Args:
            after: A dictionary mapping noise rule names to their probability argument.
                For example, {"DEPOLARIZE2": 0.01, "X_ERROR": 0.02} will add two qubit
                depolarization with parameter 0.01 and also add 2% bit flip noise. These
                noise channels occur after all other operations in the moment and are applied
                to the same targets as the relevant operation.
            flip_result: The probability that a measurement result should be reported incorrectly.
                Only valid when applied to operations that produce measurement results.

        """
        if not (0 <= flip_result <= 1):
            raise ValueError(f"not (0 <= {flip_result=} <= 1)")
        for k, p in after.items():
            if OP_TYPES[k] != NOISE:
                raise ValueError(f"not a noise channel: {k} from {after=}")
            if not (0 <= p <= 1):
                raise ValueError(f"not (0 <= {p} <= 1) from {after=}")
        self.after = after
        self.flip_result = flip_result

    def _append_noisy_version_of(
        self,
        *,
        split_op: stim.CircuitInstruction,
        out_during_moment: stim.Circuit,
        after_moments: defaultdict[tuple[str, float], stim.Circuit],
        immune_qubits: Set[int],
    ) -> None:
        targets = split_op.targets_copy()
        if immune_qubits and any(
            (t.is_qubit_target or t.is_x_target or t.is_y_target or t.is_z_target)
            and t.value in immune_qubits
            for t in targets
        ):
            out_during_moment.append(split_op)
            return

        args = split_op.gate_args_copy()
        if self.flip_result:
            t = OP_TYPES[split_op.name]
            assert t in {MPP, JUST_MEASURE_1Q, MEASURE_RESET_1Q}
            assert len(args) == 0
            args = [self.flip_result]

        out_during_moment.append(split_op.name, targets, args)
        raw_targets = [t.value for t in targets if not t.is_combiner]
        for op_name, arg in self.after.items():
            after_moments[(op_name, arg)].append(op_name, raw_targets, arg)


class NoiseModel:
    def __init__(
        self,
        idle_depolarization: float,
        additional_depolarization_waiting_for_m_or_r: float = 0,
        gate_rules: dict[str, NoiseRule] | None = None,
        measure_rules: dict[str, NoiseRule] | None = None,
        any_clifford_1q_rule: NoiseRule | None = None,
        any_clifford_2q_rule: NoiseRule | None = None,
    ):
        """Represent a noise model that can be applied to a ``stim.Circuit``."""
        self.idle_depolarization = idle_depolarization
        self.additional_depolarization_waiting_for_m_or_r = (
            additional_depolarization_waiting_for_m_or_r
        )
        self.gate_rules = gate_rules
        self.measure_rules = measure_rules
        self.any_clifford_1q_rule = any_clifford_1q_rule
        self.any_clifford_2q_rule = any_clifford_2q_rule

    @staticmethod
    def si1000(p: float) -> "NoiseModel":
        """Superconducting inspired noise.

        As defined in "A Fault-Tolerant Honeycomb Memory":
        https://arxiv.org/abs/2108.10457

        Small tweak from the paper: The measurement result is probabilistically flipped instead of
        the input qubit.

        Note that this noise model only allows Z basis measurements and resets. Currently,
        tqec does not automatically compile to compatible physical circuits.
        """
        return NoiseModel(
            idle_depolarization=p / 10,
            additional_depolarization_waiting_for_m_or_r=2 * p,
            any_clifford_1q_rule=NoiseRule(after={"DEPOLARIZE1": p / 10}),
            any_clifford_2q_rule=NoiseRule(after={"DEPOLARIZE2": p}),
            measure_rules={
                "Z": NoiseRule(after={}, flip_result=p * 5),
            },
            gate_rules={
                "R": NoiseRule(after={"X_ERROR": p * 2}),
            },
        )

    @staticmethod
    def uniform_depolarizing(p: float) -> "NoiseModel":
        """Near-standard circuit depolarizing noise.

        Everything has the same parameter ``p``. Single-qubit Clifford gates get single-qubit
        depolarization. Two-qubit Clifford gates get single-qubit depolarization. Dissipative gates
        have their result probabilistically bit-flipped (or phase-flipped if appropriate).

        Non-demolition measurement is treated a bit unusually in that it is the result that is
        flipped instead of the input qubit.

        """
        return NoiseModel(
            idle_depolarization=p,
            any_clifford_1q_rule=NoiseRule(after={"DEPOLARIZE1": p}),
            any_clifford_2q_rule=NoiseRule(after={"DEPOLARIZE2": p}),
            measure_rules={
                "X": NoiseRule(after={}, flip_result=p),
                "Y": NoiseRule(after={}, flip_result=p),
                "Z": NoiseRule(after={}, flip_result=p),
                "XX": NoiseRule(after={}, flip_result=p),
                "YY": NoiseRule(after={}, flip_result=p),
                "ZZ": NoiseRule(after={}, flip_result=p),
            },
            gate_rules={
                "RX": NoiseRule(after={"Z_ERROR": p}),
                "RY": NoiseRule(after={"X_ERROR": p}),
                "R": NoiseRule(after={"X_ERROR": p}),
            },
        )

    def _noise_rule_for_split_operation(
        self, *, split_op: stim.CircuitInstruction
    ) -> NoiseRule | None:
        if occurs_in_classical_control_system(split_op):
            return None

        if self.gate_rules is not None:
            rule = self.gate_rules.get(split_op.name)
            if rule is not None:
                return rule

        t = OP_TYPES[split_op.name]

        if self.any_clifford_1q_rule is not None and t == CLIFFORD_1Q:
            return self.any_clifford_1q_rule
        if self.any_clifford_2q_rule is not None and t == CLIFFORD_2Q:
            return self.any_clifford_2q_rule
        if self.measure_rules is not None and t in (MPP, JUST_MEASURE_1Q):
            measure_basis = _measure_basis(split_op=split_op)
            assert measure_basis is not None
            rule = self.measure_rules.get(measure_basis)
            if rule is not None:
                return rule

        raise ValueError(
            f"No noise (or lack of noise) specified for {split_op=}. Please make "
            "sure the noise model covers all operations in the compiled circuit."
        )

    def _append_idle_error(
        self,
        *,
        moment_split_ops: list[stim.CircuitInstruction],
        out: stim.Circuit,
        system_qubits: Set[int],
        immune_qubits: Set[int],
    ) -> None:
        collapse_qubits: list[int] = []
        clifford_qubits: list[int] = []
        for split_op in moment_split_ops:
            if occurs_in_classical_control_system(split_op):
                continue
            if split_op.name in COLLAPSING_OPS:
                qubits_out = collapse_qubits
            else:
                qubits_out = clifford_qubits
            for target in split_op.targets_copy():
                if not target.is_combiner:
                    qubits_out.append(target.value)

        # Safety check for operation collisions.
        usage_counts = Counter(collapse_qubits + clifford_qubits)
        qubits_used_multiple_times = {q for q, c in usage_counts.items() if c != 1}
        if qubits_used_multiple_times:
            moment = stim.Circuit()
            for op in moment_split_ops:
                moment.append(op)
            raise ValueError(
                f"Qubits were operated on multiple times without a TICK in between:\n"
                f"multiple uses: {sorted(qubits_used_multiple_times)}\n"
                f"moment:\n"
                f"{moment}"
            )

        collapse_qubits_set = set(collapse_qubits)
        clifford_qubits_set = set(clifford_qubits)
        idle = sorted(system_qubits - collapse_qubits_set - clifford_qubits_set - immune_qubits)
        if idle and self.idle_depolarization:
            out.append("DEPOLARIZE1", idle, self.idle_depolarization)

        waiting_for_mr = sorted(system_qubits - collapse_qubits_set - immune_qubits)
        if (
            collapse_qubits_set
            and waiting_for_mr
            and self.additional_depolarization_waiting_for_m_or_r
        ):
            out.append("DEPOLARIZE1", idle, self.additional_depolarization_waiting_for_m_or_r)

    def _append_noisy_moment(
        self,
        *,
        moment_split_ops: list[stim.CircuitInstruction],
        out: stim.Circuit,
        system_qubits: Set[int],
        immune_qubits: Set[int],
    ) -> None:
        after: defaultdict[tuple[str, float], stim.Circuit] = defaultdict(stim.Circuit)
        for split_op in moment_split_ops:
            rule = self._noise_rule_for_split_operation(split_op=split_op)
            if rule is None:
                out.append(split_op)
            else:
                rule._append_noisy_version_of(
                    split_op=split_op,
                    out_during_moment=out,
                    after_moments=after,
                    immune_qubits=immune_qubits,
                )
        for k in sorted(after.keys()):
            out += after[k]

        self._append_idle_error(
            moment_split_ops=moment_split_ops,
            out=out,
            system_qubits=system_qubits,
            immune_qubits=immune_qubits,
        )

    def noisy_circuit(
        self,
        circuit: stim.Circuit,
        *,
        system_qubits: set[int] | None = None,
        immune_qubits: set[int] | None = None,
    ) -> stim.Circuit:
        """Return a noisy version of the given circuit, by applying the receiving noise model.

        Args:
            circuit: The circuit to layer noise over.
            system_qubits: All qubits used by the circuit. These are the qubits eligible for idling
                noise.
            immune_qubits: Qubits to not apply noise to, even if they are operated on.

        Returns:
            The noisy version of the circuit.

        """
        if system_qubits is None:
            system_qubits = set(range(circuit.num_qubits))
        if immune_qubits is None:
            immune_qubits = set()

        result = stim.Circuit()
        for moment_split_ops in _iter_split_op_moments(circuit, immune_qubits=immune_qubits):
            if not result:
                pass
            elif isinstance(moment_split_ops, stim.CircuitRepeatBlock):
                pass
            elif isinstance(result[-1], stim.CircuitRepeatBlock):
                pass
            else:
                result.append("TICK", [], [])
            if isinstance(moment_split_ops, stim.CircuitRepeatBlock):
                noisy_body = self.noisy_circuit(
                    moment_split_ops.body_copy(),
                    system_qubits=system_qubits,
                    immune_qubits=immune_qubits,
                )
                result.append(
                    stim.CircuitRepeatBlock(
                        repeat_count=moment_split_ops.repeat_count, body=noisy_body
                    )
                )
            else:
                self._append_noisy_moment(
                    moment_split_ops=moment_split_ops,
                    out=result,
                    system_qubits=system_qubits,
                    immune_qubits=immune_qubits,
                )

        return result


def occurs_in_classical_control_system(op: stim.CircuitInstruction) -> bool:
    """Determine if an operation is an annotation or a classical control system update."""
    t = OP_TYPES[op.name]
    if t == ANNOTATION:
        return True
    if t == CLIFFORD_2Q:
        targets = op.targets_copy()
        for k in range(0, len(targets), 2):
            a = targets[k]
            b = targets[k + 1]
            classical_0 = a.is_measurement_record_target or a.is_sweep_bit_target
            classical_1 = b.is_measurement_record_target or b.is_sweep_bit_target
            if not (classical_0 or classical_1):
                return False
        return True
    return False


def _split_targets_if_needed(
    op: stim.CircuitInstruction, immune_qubits: Set[int]
) -> Iterator[stim.CircuitInstruction]:
    """Split operations into pieces as needed.

    This function splits operations, for example ``MPP`` into each product, classical control away
    from quantum ops, ...

    """
    t = OP_TYPES[op.name]
    if t == CLIFFORD_2Q:
        yield from _split_targets_if_needed_clifford_2q(op, immune_qubits)
    elif t == MPP:
        yield from _split_targets_if_needed_m_basis(op, immune_qubits)
    elif t in [NOISE, ANNOTATION]:
        yield op
    else:
        yield from _split_targets_if_needed_clifford_1q(op, immune_qubits)


def _split_targets_if_needed_clifford_1q(
    op: stim.CircuitInstruction, immune_qubits: Set[int]
) -> Iterator[stim.CircuitInstruction]:
    if immune_qubits:
        args = op.gate_args_copy()
        for t in op.targets_copy():
            yield stim.CircuitInstruction(op.name, [t], args)
    else:
        yield op


def _split_targets_if_needed_clifford_2q(
    op: stim.CircuitInstruction, immune_qubits: Set[int]
) -> Iterator[stim.CircuitInstruction]:
    """Split classical control system operations away from quantum operations."""
    assert OP_TYPES[op.name] == CLIFFORD_2Q
    targets = op.targets_copy()
    if immune_qubits or any(t.is_measurement_record_target for t in targets):
        args = op.gate_args_copy()
        for k in range(0, len(targets), 2):
            yield stim.CircuitInstruction(op.name, targets[k : k + 2], args)
    else:
        yield op


def _split_targets_if_needed_m_basis(
    op: stim.CircuitInstruction, immune_qubits: Set[int]
) -> Iterator[stim.CircuitInstruction]:
    """Split an MPP operation into one operation for each Pauli product it measures."""
    targets = op.targets_copy()
    args = op.gate_args_copy()
    k = 0
    start = k
    while k < len(targets):
        if k + 1 == len(targets) or not targets[k + 1].is_combiner:
            yield stim.CircuitInstruction(op.name, targets[start : k + 1], args)
            k += 1
            start = k
        else:
            k += 2
    assert k == len(targets)


def _iter_split_op_moments(
    circuit: stim.Circuit, *, immune_qubits: Set[int]
) -> Iterator[stim.CircuitRepeatBlock | list[stim.CircuitInstruction]]:
    """Split a circuit into moments and some operations into pieces.

    Classical control system operations like ``CX rec[-1] 0`` are split from quantum operations
    like ``CX 1 0``.

    MPP operations are split into one operation per Pauli product.

    Yields:
        Lists of operations corresponding to one moment in the circuit, with any problematic
        operations like MPPs split into pieces.

        (A moment is the time between two TICKs.)

    """
    cur_moment: list[stim.CircuitInstruction] = []

    for op in circuit:
        if isinstance(op, stim.CircuitRepeatBlock):
            if cur_moment:
                yield cur_moment
                cur_moment = []
            yield op
        elif op.name == "TICK":
            yield cur_moment
            cur_moment = []
        else:
            cur_moment.extend(_split_targets_if_needed(op, immune_qubits=immune_qubits))
    if cur_moment:
        yield cur_moment


def _measure_basis(*, split_op: stim.CircuitInstruction) -> str | None:
    """Convert an operation into a string describing the Pauli product basis it measures.

    Returns:
        None: This is not a measurement (or not *just* a measurement).
        str: Pauli product string that the operation measures (e.g. "XX" or "Y").

    """
    result = OP_MEASURE_BASES.get(split_op.name)
    if result == "":
        targets = split_op.targets_copy()
        for k in range(0, len(targets), 2):
            t = targets[k]
            if t.is_x_target:
                result += "X"
            elif t.is_y_target:
                result += "Y"
            elif t.is_z_target:
                result += "Z"
            else:
                raise NotImplementedError(f"{targets=}")
    return result
