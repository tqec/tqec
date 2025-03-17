from tqec.compile.specs.base import CubeBuilder, PipeBuilder
from tqec.compile.specs.library.base import BaseCubeBuilder, BasePipeBuilder
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler

STANDARD_CUBE_BUILDER: CubeBuilder = BaseCubeBuilder(IdentityPlaquetteCompiler)
STANDARD_PIPE_BUILDER: PipeBuilder = BasePipeBuilder(IdentityPlaquetteCompiler)
