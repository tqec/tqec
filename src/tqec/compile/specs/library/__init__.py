from typing import Final

from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder

from .standard import STANDARD_BLOCK_BUILDER as STANDARD_BLOCK_BUILDER
from .standard import STANDARD_SUBSTITUTION_BUILDER as STANDARD_SUBSTITUTION_BUILDER

ALL_SPECS: Final[dict[str, tuple[BlockBuilder, SubstitutionBuilder]]] = {
    "STANDARD": (STANDARD_BLOCK_BUILDER, STANDARD_SUBSTITUTION_BUILDER),
}
