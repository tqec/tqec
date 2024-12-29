from abc import ABC, abstractmethod
from typing import Iterable

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.plaquette import Plaquette


class PlaquetteCompiler:
    def __init__(self, passes: Iterable[CompilationPass]):
        super().__init__()
        self._passes = passes

    def compile(self, plaquette: Plaquette) -> Plaquette:
        circuit = plaquette.circuit.get_circuit(include_qubit_coords=True)
        for compilation_pass in self._passes:
            circuit = compilation_pass.run(circuit)

        # TODO: issue here, how to be sure we respect the input schedule?
        return plaquette
