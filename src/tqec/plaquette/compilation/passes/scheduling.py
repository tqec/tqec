from dataclasses import dataclass

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.utils.exceptions import TQECError


@dataclass
class ScheduleMap:
    """Represent a map from schedules to schedules."""

    map: dict[int, int]

    def apply(self, circuit: ScheduledCircuit) -> ScheduledCircuit:
        """Apply the schedule map.

        This method will create a new
        :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` instance, only
        including the moments from the provided ``circuit`` if they are present
        as keys in ``self.map``, and mapping them to the schedule at the
        corresponding value.

        Args:
            circuit: circuit whose schedules should be modified.

        Returns:
            a new circuit with moments scheduled according to the values in
            ``self.map``.

        Raises:
            TQECError: if a moment in the provided ``circuit`` is scheduled
                at a time that is not present in ``self.map``.
            TQECError: if re-organising the schedules lead to an invalid
                circuit (i.e., at least one moment with overlapping operations).
                That can only happen if ``self.map.values()`` contains duplicate
                integers.

        """
        ret = ScheduledCircuit([], [], circuit.qubit_map)
        for moment_index, moment in circuit.scheduled_moments:
            if moment_index not in self.map:
                raise TQECError(
                    f"Found a moment scheduled at {moment_index} but this "
                    "schedule is not included in the schedule map."
                )
            new_schedule = self.map[moment_index]
            ret.add_to_schedule_index(new_schedule, moment)
        return ret


class ChangeSchedulePass(CompilationPass):
    def __init__(self, schedule_map: dict[int, int]):
        """Compilation pass changing the schedule of the provided quantum circuit."""
        super().__init__()
        self._map = ScheduleMap(schedule_map)

    @override
    def run(self, circuit: ScheduledCircuit, check_all_flows: bool = False) -> ScheduledCircuit:
        modified_circuit = self._map.apply(circuit)
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)  # pragma: no cover
        return modified_circuit
