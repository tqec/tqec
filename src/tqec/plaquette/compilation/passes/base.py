from abc import ABC, abstractmethod

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.exceptions import TQECException


class CompilationPass(ABC):
    @abstractmethod
    def run(
        self, circuit: ScheduledCircuit, check_all_flows: bool = False
    ) -> ScheduledCircuit:
        pass

    def check_flows(
        self, original_circuit: ScheduledCircuit, modified_circuit: ScheduledCircuit
    ) -> None:
        original_flows = original_circuit.get_circuit().flow_generators()
        if not modified_circuit.get_circuit().has_all_flows(original_flows):
            raise TQECException("Modified circuit does not contain")
