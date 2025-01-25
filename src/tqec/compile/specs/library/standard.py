from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder
from tqec.compile.specs.library.base import BaseBlockBuilder, BaseSubstitutionBuilder
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler

STANDARD_BLOCK_BUILDER: BlockBuilder = BaseBlockBuilder(IdentityPlaquetteCompiler)
STANDARD_SUBSTITUTION_BUILDER: SubstitutionBuilder = BaseSubstitutionBuilder(
    IdentityPlaquetteCompiler
)
