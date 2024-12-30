from abc import ABC, abstractmethod
from typing import Final, Sequence

import stim
from typing_extensions import override


class InstructionSimplifier(ABC):
    @abstractmethod
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        pass


class NoInstructionSimplification(InstructionSimplifier):
    @override
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        return list(instructions)


class SelfInverseGateSimplification(InstructionSimplifier):
    SELF_INVERSE_GATES: Final[frozenset[str]] = frozenset(["H", "X", "Y", "Z"])

    @override
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        ret: list[stim.CircuitInstruction] = []
        gate_counter: dict[
            tuple[str, tuple[stim.GateTarget, ...], tuple[float, ...]], int
        ] = {}
        for instruction in instructions:
            if instruction.name not in SelfInverseGateSimplification.SELF_INVERSE_GATES:
                ret.append(instruction)
            args = tuple(instruction.gate_args_copy())
            for target_group in instruction.target_groups():
                key = (instruction.name, tuple(target_group), args)
                gate_counter[key] = gate_counter.get(key, 0) + 1
        gates_to_apply: dict[tuple[str, tuple[float, ...]], list[stim.GateTarget]] = {}
        for (name, target_group, args), count in gate_counter.items():
            if count % 2 == 1:
                gates_to_apply.setdefault((name, args), []).extend(target_group)
        for (name, args), targets in gates_to_apply.items():
            ret.append(stim.CircuitInstruction(name, targets, args))
        return ret
