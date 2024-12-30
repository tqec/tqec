from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import stim
from typing_extensions import override

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass


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


class ScheduleFunction(ABC):
    @abstractmethod
    def __call__(self, input_schedule: int) -> int:
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass


class ScheduleOffset(ScheduleFunction):
    def __init__(self, offset: int):
        super().__init__()
        self._offset = offset

    @override
    def __call__(self, input_schedule: int) -> int:
        return input_schedule + self._offset

    @override
    def __hash__(self) -> int:
        return 2 * self._offset


class ScheduleConstant(ScheduleFunction):
    def __init__(self, constant: int):
        super().__init__()
        self._constant = constant

    @override
    def __call__(self, input_schedule: int) -> int:
        return self._constant

    @override
    def __hash__(self) -> int:
        return 2 * self._constant + 1


@dataclass
class ScheduledCircuitTransformation:
    source_name: str
    transformation: dict[ScheduleFunction, list[InstructionCreator]]

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        moments: dict[int, Moment] = {}
        for schedule, moment in circuit.scheduled_moments:
            for instruction in moment.instructions:
                if instruction.name != self.source_name:
                    moments.setdefault(schedule, Moment(stim.Circuit())).append(
                        instruction
                    )
                    continue
                targets = instruction.targets_copy()
                args = instruction.gate_args_copy()
                for schedule_function, instr_creators in self.transformation.items():
                    sched: int = schedule_function(schedule)
                    moment = moments.setdefault(sched, Moment(stim.Circuit()))
                    for creator in instr_creators:
                        moment.append(creator(targets, args))
        schedules = sorted(moments.keys())
        all_moments = [moments[s] for s in schedules]
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
        self, transformations: Sequence[ScheduledCircuitTransformation]
    ) -> None:
        super().__init__()
        self._transformations = ScheduledCircuitTransformer(transformations)

    @override
    def run(
        self,
        circuit: ScheduledCircuit,
        check_all_flows: bool = False,
    ) -> ScheduledCircuit:
        modified_circuit = self._transformations.apply(circuit)
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)
        return modified_circuit
