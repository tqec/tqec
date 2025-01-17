from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder
from tqec.compile.specs.library.base import BaseBlockBuilder, BaseSubstitutionBuilder
from tqec.plaquette.compilation.css import CSSPlaquetteCompiler

CSS_BLOCK_BUILDER: BlockBuilder = BaseBlockBuilder(CSSPlaquetteCompiler)
CSS_SUBSTITUTION_BUILDER: SubstitutionBuilder = BaseSubstitutionBuilder(
    CSSPlaquetteCompiler
)
