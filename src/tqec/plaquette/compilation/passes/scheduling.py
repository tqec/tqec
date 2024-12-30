from dataclasses import dataclass

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.exceptions import TQECException
from tqec.plaquette.compilation.passes.base import CompilationPass


@dataclass
class ScheduleMap:
    map: dict[int, int]

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        ret = ScheduledCircuit([], [], circuit.qubit_map)
        for moment_index, moment in circuit.scheduled_moments:
            if moment_index not in self.map:
                raise TQECException(
                    f"Found a moment scheduled at {moment_index} but this "
                    "schedule is not included in the schedule map."
                )
            new_schedule = self.map[moment_index]
            ret.add_to_schedule_index(new_schedule, moment)
        return ret


class ChangeSchedulePass(CompilationPass):
    def __init__(self, schedule_map: ScheduleMap):
        super().__init__()
        self._map = schedule_map

    @override
    def run(
        self, circuit: ScheduledCircuit, check_all_flows: bool = False
    ) -> ScheduledCircuit:
        modified_circuit = self._map.apply(circuit)
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)
        return modified_circuit
