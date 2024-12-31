"""Introduces :class:`~tqec.plaquette.compilation.base.PlaquetteCompiler`, the class
used to implement a plaquette compiler."""

from typing import Iterable

from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.plaquette import Plaquette


class PlaquetteCompiler:
    def __init__(self, name: str, passes: Iterable[CompilationPass]):
        """A wrapper around a list of
        :class:`~tqec.plaquette.compilation.passes.base.CompilationPass` instances."""
        super().__init__()
        self._name = name
        self._passes = passes

    def compile(self, plaquette: Plaquette) -> Plaquette:
        """Apply in order all the stored compilation passes and returns the
        resulting plaquette."""
        circuit = plaquette.circuit
        for compilation_pass in self._passes:
            circuit = compilation_pass.run(circuit)
        return Plaquette(
            f"{plaquette.name}_{self._name}",
            plaquette.qubits,
            circuit,
            plaquette.mergeable_instructions,
        )