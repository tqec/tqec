from typing import Final

from tqec.compile.specs.base import CubeBuilder, PipeBuilder

from .fixed_bulk import FIXED_BULK_CUBE_BUILDER as FIXED_BULK_CUBE_BUILDER
from .fixed_bulk import FIXED_BULK_PIPE_BUILDER as FIXED_BULK_PIPE_BUILDER
from .standard import STANDARD_CUBE_BUILDER as STANDARD_CUBE_BUILDER
from .standard import STANDARD_PIPE_BUILDER as STANDARD_PIPE_BUILDER

ALL_SPECS: Final[dict[str, tuple[CubeBuilder, PipeBuilder]]] = {
    "STANDARD": (STANDARD_CUBE_BUILDER, STANDARD_PIPE_BUILDER),
    "FIXED_BULK": (FIXED_BULK_CUBE_BUILDER, FIXED_BULK_PIPE_BUILDER),
}
