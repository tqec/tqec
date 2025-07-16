from abc import ABC, abstractmethod
from collections.abc import Sequence

import stim
from typing_extensions import override


class InstructionSimplifier(ABC):
    """Base interface for classes to simplify operations.

    Compilation passes often need to introduce new gates in several moments. It
    might happen that these newly inserted gates are already present in the
    moment (which is often the case for the ``H`` gate). This class offers an
    interface to try to simplify those gates when it is possible, before raising
    an exception because the moment is invalid.

    """

    @abstractmethod
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        """Simplify a list of instructions that are happening at the same moment in the circuit."""
        pass


class NoInstructionSimplification(InstructionSimplifier):
    @override
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        return list(instructions)


class SelfInverseGateSimplification(InstructionSimplifier):
    def __init__(self, *self_inverse_gates: str):
        """Compilation pass simplifying self-inverse gates when applied more than once."""
        super().__init__()
        self._self_inverse_gates = frozenset(self_inverse_gates)

    @override
    def simplify(
        self, instructions: Sequence[stim.CircuitInstruction]
    ) -> list[stim.CircuitInstruction]:
        # Append in ret all the instructions that are not in
        # self._self_inverse_gates and count the instructions that are in it.
        ret: list[stim.CircuitInstruction] = []
        gate_counter: dict[tuple[str, tuple[stim.GateTarget, ...], tuple[float, ...]], int] = {}
        for instruction in instructions:
            if instruction.name not in self._self_inverse_gates:
                ret.append(instruction)
                continue
            args = tuple(instruction.gate_args_copy())
            for target_group in instruction.target_groups():
                key = (instruction.name, tuple(target_group), args)
                gate_counter[key] = gate_counter.get(key, 0) + 1
        # Instructions in gate_counter are marked as self-inverse. An odd number
        # of such instructions is equivalent to applying the instruction once.
        # An even number is equivalent to not applying the instruction.
        # Not inserting directly into ret yet to group instructions by name in
        # the final instruction list.
        gates_to_apply: dict[tuple[str, tuple[float, ...]], list[stim.GateTarget]] = {}
        for (name, target_group, args), count in gate_counter.items():
            if count % 2 == 1:
                gates_to_apply.setdefault((name, args), []).extend(target_group)
        for (name, args), targets in gates_to_apply.items():
            ret.append(stim.CircuitInstruction(name, targets, args))
        return ret
