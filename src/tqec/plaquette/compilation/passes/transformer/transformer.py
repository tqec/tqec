from dataclasses import dataclass
from typing import Callable, Sequence

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
    name: str
    targets: Callable[[list[stim.GateTarget]], list[stim.GateTarget]] = (
        lambda trgts: trgts
    )
    arguments: Callable[[list[float]], list[float]] = lambda args: args

    def __call__(
        self, targets: list[stim.GateTarget], arguments: list[float]
    ) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            self.name, self.targets(targets), self.arguments(arguments)
        )


@dataclass
class ScheduledCircuitTransformation:
    source_name: str
    transformation: dict[ScheduleFunction, list[InstructionCreator]]
    instruction_simplifier: InstructionSimplifier = NoInstructionSimplification()

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        moment_instructions: dict[int, list[stim.CircuitInstruction]] = {}
        for schedule, moment in circuit.scheduled_moments:
            for instruction in moment.instructions:
                if instruction.name != self.source_name:
                    moment_instructions.setdefault(schedule, []).append(instruction)
                    continue
                targets = instruction.targets_copy()
                args = instruction.gate_args_copy()
                for schedule_function, instr_creators in self.transformation.items():
                    sched: int = schedule_function(schedule)
                    moment = moment_instructions.setdefault(sched, [])
                    for creator in instr_creators:
                        moment.append(creator(targets, args))
        schedules = sorted(moment_instructions.keys())
        all_moments = [
            Moment.from_instructions(
                self.instruction_simplifier.simplify(moment_instructions[s])
            )
            for s in schedules
        ]
        return ScheduledCircuit(all_moments, schedules, circuit.qubit_map)


class ScheduledCircuitTransformer:
    def __init__(
        self, transformations: Sequence[ScheduledCircuitTransformation]
    ) -> None:
        self._transformations = transformations

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        for transformation in self._transformations:
            circuit = transformation.apply(circuit)
        return circuit


class ScheduledCircuitTransformationPass(CompilationPass):
    def __init__(
        self,
        transformations: Sequence[ScheduledCircuitTransformation],
    ) -> None:
        super().__init__()
        self._transformations = ScheduledCircuitTransformer(transformations)

    @override
    def run(
        self, circuit: ScheduledCircuit, check_all_flows: bool = False
    ) -> ScheduledCircuit:
        modified_circuit = self._transformations.apply(circuit)
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)
        return modified_circuit