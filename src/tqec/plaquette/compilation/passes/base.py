from abc import ABC, abstractmethod

import stim

from tqec.exceptions import TQECException


class CompilationPass(ABC):
    @abstractmethod
    def run(self, circuit: stim.Circuit, check_all_flows: bool = False) -> stim.Circuit:
        pass

    def check_flows(
        self, original_circuit: stim.Circuit, modified_circuit: stim.Circuit
    ) -> None:
        original_flows = original_circuit.flow_generators()
        if not modified_circuit.has_all_flows(original_flows):
            raise TQECException("Modified circuit does not contain")
