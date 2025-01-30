"""Defines the data-structures used to obtain correct
:class:`tqec.compile.block.CompiledBlock` instances for different sets of
plaquettes."""

from .base import BlockBuilder as BlockBuilder
from .base import CubeSpec as CubeSpec
from .base import PipeSpec as PipeSpec
from .base import SubstitutionBuilder as SubstitutionBuilder
from .library import STANDARD_BLOCK_BUILDER as STANDARD_BLOCK_BUILDER
from .library import STANDARD_SUBSTITUTION_BUILDER as STANDARD_SUBSTITUTION_BUILDER
