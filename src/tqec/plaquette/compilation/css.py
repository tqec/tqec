from typing_extensions import override

from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.compilation.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)
from tqec.plaquette.compilation.passes.reset_basis import ChangeResetBasisPass
from tqec.plaquette.enums import MeasurementBasis, ResetBasis

CSSPlaquetteCompiler = PlaquetteCompiler(
    [ChangeResetBasisPass(ResetBasis.Z), ChangeMeasurementBasisPass(MeasurementBasis.Z)]
)
