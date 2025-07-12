from abc import ABC, abstractmethod

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.utils.exceptions import TQECError


class CompilationPass(ABC):
    """Base interface that should be implemented by all compilation passes."""

    @abstractmethod
    def run(self, circuit: ScheduledCircuit, check_all_flows: bool = False) -> ScheduledCircuit:
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
        """Check that the two provided circuits have the exact same flows.

        This method can be used to check if two quantum circuits are functionally
        equivalent. It lists all the flows of the provided ``original_circuit``
        and checks that ``modified_circuit`` contains all these flows.

        Args:
            original_circuit: first circuit, supposed to be the circuit before
                applying the compilation pass.
            modified_circuit: second circuit, supposed to be the circuit after
                applying the compilation pass.

        Raises:
            TQECError: if the two provided circuits are not functionally
                equivalent (i.e. ``modified_circuit`` does not have at least
                one of flow of ``original_circuit``).

        """
        original_flows = original_circuit.get_circuit().flow_generators()
        if not modified_circuit.get_circuit().has_all_flows(original_flows):
            raise TQECError("Modified circuit does not contain")
