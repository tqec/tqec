from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import stim
from typing_extensions import override

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.compilation.passes.transformer.schedule import ScheduleFunction
from tqec.plaquette.compilation.passes.transformer.simplifiers import (
    InstructionSimplifier,
    NoInstructionSimplification,
)


@dataclass
class InstructionCreator:
    """Create an instruction from targets and arguments."""

    name: str
    targets: Callable[[list[stim.GateTarget]], list[stim.GateTarget]] = lambda trgts: trgts
    arguments: Callable[[list[float]], list[float]] = lambda args: args

    def __call__(
        self, targets: list[stim.GateTarget], arguments: list[float]
    ) -> stim.CircuitInstruction:
        """Create a ``stim.CircuitInstruction`` from the provided arguments."""
        return stim.CircuitInstruction(self.name, self.targets(targets), self.arguments(arguments))


@dataclass
class ScheduledCircuitTransformation:
    """Describes an instruction transformation.

    This class describes how a given instruction should be transformed into
    potentially several instructions.

    Attributes:
        source_name: name of the instruction that is transformed by ``self``.
        transformation: a mapping from a schedule description to a list of
            instruction creators. The instructions created by the instruction
            creators will be inserted at the schedule computed by the schedule
            description.
        instruction_simplifier: a simplifier applied before trying to create a
            :class:`~tqec.circuit.moment.Moment` instance with the instructions
            resulting from the application of ``self``.

    """

    source_name: str
    transformation: dict[ScheduleFunction, list[InstructionCreator]]
    instruction_simplifier: InstructionSimplifier = field(
        default_factory=NoInstructionSimplification
    )

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        """Apply the transformation to ``circuit`` and return the result."""
        # moment_instructions: schedule_index -> instruction list.
        moment_instructions: dict[int, list[stim.CircuitInstruction]] = {}
        for schedule, moment in circuit.scheduled_moments:
            for instruction in moment.instructions:
                # if the transformation represented by self does not apply to
                # the current instruction, just add it unmodified.
                if instruction.name not in stim.gate_data(self.source_name).aliases:
                    moment_instructions.setdefault(schedule, []).append(instruction)
                    continue
                # else, for each instruction creator in self.transformation, add
                # the created instruction to the target moment.
                targets = instruction.targets_copy()
                args = instruction.gate_args_copy()
                for schedule_function, instr_creators in self.transformation.items():
                    sched: int = schedule_function(schedule)
                    moment_instructions.setdefault(sched, []).extend(
                        creator(targets, args) for creator in instr_creators
                    )
        # Make sure that the schedules are given to ScheduledCircuit as a
        # sorted list.
        schedules = sorted(moment_instructions.keys())
        all_moments = [
            Moment.from_instructions(
                # Try to simplify operations before creating the moment.
                self.instruction_simplifier.simplify(moment_instructions[s])
            )
            for s in schedules
        ]
        return ScheduledCircuit(all_moments, schedules, circuit.qubit_map)


class ScheduledCircuitTransformer:
    def __init__(self, transformations: Sequence[ScheduledCircuitTransformation]) -> None:
        """Describe a list of :class:`ScheduledCircuitTransformation` instances.

        Note:
            This class has been introduced for convenience and for future
            optimisation. Right now, a new scheduled circuit is created for each
            :class:`ScheduledCircuitTransformation` instance in ``self``. This is
            suboptimal as we might be able to apply all the transformations by
            iterating the original quantum circuit once.

            Due to the very limited size of the circuits given to the compilation
            pipeline, this performance issue does not seem to have a measurable
            impact at the moment.

        """
        self._transformations = transformations

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        """Apply the transformations stored in ``self`` to ``circuit`` and return the result."""
        for transformation in self._transformations:
            circuit = transformation.apply(circuit)
        return circuit


class ScheduledCircuitTransformationPass(CompilationPass):
    def __init__(
        self,
        transformations: Sequence[ScheduledCircuitTransformation],
    ) -> None:
        """Apply the provided transformations as a compilation pass.

        Args:
            transformations: a sequence of transformation that are applied one after the other.

        """
        super().__init__()
        self._transformations = ScheduledCircuitTransformer(transformations)

    @override
    def run(self, circuit: ScheduledCircuit, check_all_flows: bool = False) -> ScheduledCircuit:
        modified_circuit = self._transformations.apply(circuit)
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)  # pragma: no cover
        return modified_circuit
