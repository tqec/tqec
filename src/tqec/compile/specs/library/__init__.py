from typing import Final

from tqec.compile.specs.base import CubeBuilder, PipeBuilder

from .standard import STANDARD_CUBE_BUILDER as STANDARD_CUBE_BUILDER
from .standard import STANDARD_PIPE_BUILDER as STANDARD_PIPE_BUILDER
from .css import CSS_BLOCK_BUILDER as CSS_BLOCK_BUILDER
from .css import CSS_SUBSTITUTION_BUILDER as CSS_SUBSTITUTION_BUILDER
from .zxxz import ZXXZ_BLOCK_BUILDER as ZXXZ_BLOCK_BUILDER
from .zxxz import ZXXZ_SUBSTITUTION_BUILDER as ZXXZ_SUBSTITUTION_BUILDER

ALL_SPECS: Final[dict[str, tuple[CubeBuilder, PipeBuilder]]] = {
    "STANDARD": (STANDARD_CUBE_BUILDER, STANDARD_PIPE_BUILDER),
}
