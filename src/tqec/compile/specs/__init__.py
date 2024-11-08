"""Defines the data-structures used to obtain correct
:class:`tqec.compile.block.CompiledBlock` instances for different sets of
plaquettes."""

from .base import BlockBuilder, CubeSpec, PipeSpec, SubstitutionBuilder
from .library import (
    CSS_BLOCK_BUILDER,
    CSS_SUBSTITUTION_BUILDER,
    ZXXZ_BLOCK_BUILDER,
    ZXXZ_SUBSTITUTION_BUILDER,
)
