from typing import Final

from tqec.compile.blocks.block import Block
from tqec.compile.specs.base import (
    CubeBuilder,
    CubeSpec,
    PipeBuilder,
    PipeSpec,
)
from tqec.compile.specs.library.generators.fixed_parity import (
    FixedParityConventionGenerator,
)
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.scale import LinearFunction

_DEFAULT_BLOCK_REPETITIONS: Final[LinearFunction] = LinearFunction(2, -1)


class FixedParityCubeBuilder(CubeBuilder):
    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Implementation of the :class:`~tqec.compile.specs.base.CubeBuilder`
        interface for the fixed parity convention.

        This class provides an implementation following the fixed-parity convention.
        This convention consists in the fact that 2-body stabilizers on the boundary
        of a logical qubit are always at an even parity.
        """
        self._generator = FixedParityConventionGenerator(translator, compiler)

    def __call__(self, spec: CubeSpec) -> Block:
        raise NotImplementedError("Fixed parity builder is not implemented yet.")


class FixedParityPipeBuilder(PipeBuilder):
    def __init__(
        self,
        compiler: PlaquetteCompiler,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
    ) -> None:
        """Implementation of the :class:`~tqec.compile.specs.base.PipeBuilder`
        interface for the fixed parity convention.

        This class provides an implementation following the fixed-parity convention.
        This convention consists in the fact that 2-body stabilizers on the boundary
        of a logical qubit are always at an even parity.
        """
        self._generator = FixedParityConventionGenerator(translator, compiler)

    def __call__(self, spec: PipeSpec) -> Block:
        raise NotImplementedError("Fixed parity pipe builder is not implemented yet.")


FIXED_PARITY_CUBE_BUILDER = FixedParityCubeBuilder(IdentityPlaquetteCompiler)
FIXED_PARITY_PIPE_BUILDER = FixedParityPipeBuilder(IdentityPlaquetteCompiler)
