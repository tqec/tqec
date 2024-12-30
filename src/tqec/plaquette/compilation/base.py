from abc import ABC, abstractmethod
from typing import Iterable

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.plaquette import Plaquette


class PlaquetteCompiler:
    def __init__(self, name: str, passes: Iterable[CompilationPass]):
        super().__init__()
        self._name = name
        self._passes = passes

    def compile(self, plaquette: Plaquette) -> Plaquette:
        circuit = plaquette.circuit
        for compilation_pass in self._passes:
            circuit = compilation_pass.run(circuit)
        return Plaquette(
            f"{plaquette.name}_{self._name}",
            plaquette.qubits,
            circuit,
            plaquette.mergeable_instructions,
        )
