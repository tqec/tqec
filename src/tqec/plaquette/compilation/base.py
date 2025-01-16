"""Introduces :class:`~tqec.plaquette.compilation.base.PlaquetteCompiler`, the class
used to implement a plaquette compiler."""

from typing import Callable, Final, Iterable

from tqec.plaquette.compilation.passes.base import CompilationPass
from tqec.plaquette.plaquette import Plaquette


class PlaquetteCompiler:
    def __init__(
        self,
        name: str,
        passes: Iterable[CompilationPass],
        mergeable_instructions_modifier: Callable[[frozenset[str]], frozenset[str]],
    ):
        """A wrapper around a list of
        :class:`~tqec.plaquette.compilation.passes.base.CompilationPass` instances."""
        self._name = name
        self._passes = passes
        self._mergeable_instructions_modifier = mergeable_instructions_modifier

    def compile(self, plaquette: Plaquette) -> Plaquette:
        """Apply in order all the stored compilation passes and returns the
        resulting plaquette.

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
            f"{plaquette.name}_{self._name}",
            plaquette.qubits,
            circuit,
            self._mergeable_instructions_modifier(plaquette.mergeable_instructions),
        )


IdentityPlaquetteCompiler: Final[PlaquetteCompiler] = PlaquetteCompiler(
    "ID", [], lambda x: x
)
