from abc import ABC, abstractmethod

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.exceptions import TQECException


class CompilationPass(ABC):
    """Base interface that should be implemented by all compilation passes."""

    @abstractmethod
    def run(
        self, circuit: ScheduledCircuit, check_all_flows: bool = False
    ) -> ScheduledCircuit:
        """Run the compilation pass.

        Args:
            circuit: quantum circuit that should be modified by the compilation
                pass.
            check_all_flows: if ``True``, this method will check if the final
                compiled circuit has the same Pauli flows as the original
                circuit. This check may be costly in terms of runtime, so it is
                disabled by default.

        Returns:
            the compiled quantum circuit.
        """
        pass

    def check_flows(
        self, original_circuit: ScheduledCircuit, modified_circuit: ScheduledCircuit
    ) -> None:
        original_flows = original_circuit.get_circuit().flow_generators()
        if not modified_circuit.get_circuit().has_all_flows(original_flows):
            raise TQECException("Modified circuit does not contain")
