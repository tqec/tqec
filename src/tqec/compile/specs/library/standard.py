from tqec.compile.specs.base import CubeBuilder, PipeBuilder
from tqec.compile.specs.library.fixed_bulk import (
    FIXED_BULK_CUBE_BUILDER,
    FIXED_BULK_PIPE_BUILDER,
)

STANDARD_CUBE_BUILDER: CubeBuilder = FIXED_BULK_CUBE_BUILDER
STANDARD_PIPE_BUILDER: PipeBuilder = FIXED_BULK_PIPE_BUILDER
