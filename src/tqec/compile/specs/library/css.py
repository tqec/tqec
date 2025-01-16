from functools import partial

from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder
from tqec.compile.specs.library._utils import (
    default_compiled_block_builder,
    default_substitution_builder,
)
from tqec.plaquette.library.css import make_css_surface_code_plaquette

CSS_BLOCK_BUILDER: BlockBuilder = partial(
    default_compiled_block_builder, plaquette_builder=make_css_surface_code_plaquette
)

CSS_SUBSTITUTION_BUILDER: SubstitutionBuilder = partial(
    default_substitution_builder, plaquette_builder=make_css_surface_code_plaquette
)
