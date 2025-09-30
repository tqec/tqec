"""Introduces :class:`.PlaquetteCompiler`, the class used to implement a plaquette compiler."""

from collections.abc import Callable, Iterable
from typing import Final

from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.plaquette import Plaquette
from tqec.utils.instructions import (
    MEASUREMENT_INSTRUCTION_NAMES,
    RESET_INSTRUCTION_NAMES,
)


class PlaquetteCompiler:
    def __init__(
        self,
        name: str,
        passes: Iterable[CompilationPass],
        mergeable_instructions_modifier: Callable[[frozenset[str]], frozenset[str]],
    ):
        """Wrap a list of :class:`.CompilationPass` instances."""
        self._name = name
        self._passes = passes
        self._mergeable_instructions_modifier = mergeable_instructions_modifier

    def compile(self, plaquette: Plaquette) -> Plaquette:
        """Apply all the stored compilation passes in order and return the resulting plaquette.

        Args:
            plaquette: plaquette to compile.

        Returns:
            a :class:`~tqec.plaquette.plaquette.Plaquette` instance that has been
            compiled with the compilation passes stored in ``self`` and with a
            modified name.

        """
        circuit = plaquette.circuit
        for compilation_pass in self._passes:
            circuit = compilation_pass.run(circuit)
        return Plaquette(
            f"{self._name}({plaquette.name})",
            plaquette.qubits,
            circuit,
            self._mergeable_instructions_modifier(plaquette.mergeable_instructions),
            plaquette.debug_information,
        )


IdentityPlaquetteCompiler: Final[PlaquetteCompiler] = PlaquetteCompiler(
    "ID", [], lambda x: x | MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES
)
