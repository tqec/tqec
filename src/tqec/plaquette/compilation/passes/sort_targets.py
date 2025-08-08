import functools
import operator
from collections.abc import Iterator

import stim
from typing_extensions import override

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass


def _with_targets_sorted(moments: Iterator[Moment]) -> list[Moment]:
    ret_moments: list[Moment] = []
    for moment in moments:
        circuit = stim.Circuit()
        for instruction in moment.instructions:
            target_groups = instruction.target_groups()
            target_groups.sort(key=lambda group: [trgt.value for trgt in group])
            targets: list[stim.GateTarget] = functools.reduce(operator.iadd, target_groups, [])
            circuit.append(instruction.name, targets, instruction.gate_args_copy())
        ret_moments.append(Moment(circuit, moment.qubits_indices, _avoid_checks=True))
    return ret_moments


class SortTargetsPass(CompilationPass):
    """Compilation pass sorting the targets of the provided quantum circuit instructions."""

    @override
    def run(self, circuit: ScheduledCircuit, check_all_flows: bool = False) -> ScheduledCircuit:
        modified_circuit = ScheduledCircuit(
            _with_targets_sorted(circuit.moments), circuit.schedule, circuit.qubit_map
        )
        if check_all_flows:
            self.check_flows(circuit, modified_circuit)  # pragma: no cover
        return modified_circuit
