from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.compilation.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)
from tqec.plaquette.compilation.passes.reset_basis import ChangeResetBasisPass
from tqec.plaquette.compilation.passes.scheduling import ChangeSchedulePass, ScheduleMap
from tqec.plaquette.enums import MeasurementBasis, ResetBasis

CSSPlaquetteCompiler = PlaquetteCompiler(
    "CSS",
    [
        # Move schedules to have an empty schedule for basis change after resets
        # and before measurements.
        ChangeSchedulePass(ScheduleMap({0: 0, 6: 8} | {i: i + 1 for i in range(1, 6)})),
        ChangeResetBasisPass(ResetBasis.Z),
        ChangeMeasurementBasisPass(MeasurementBasis.Z),
    ],
)
