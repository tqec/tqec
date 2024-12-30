from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.compilation.passes.controlled_gate_basis import (
    ChangeControlledGateBasisPass,
)
from tqec.plaquette.compilation.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)
from tqec.plaquette.compilation.passes.reset_basis import ChangeResetBasisPass
from tqec.plaquette.compilation.passes.scheduling import ChangeSchedulePass, ScheduleMap
from tqec.plaquette.compilation.passes.transformer import ScheduleConstant
from tqec.plaquette.enums import Basis, MeasurementBasis, ResetBasis

CSSPlaquetteCompiler = PlaquetteCompiler(
    "CSS",
    [
        # Move schedules to have an empty schedule for basis change after resets
        # and before measurements.
        ChangeSchedulePass(ScheduleMap({0: 0, 6: 8} | {i: i + 1 for i in range(1, 6)})),
        ChangeResetBasisPass(Basis.Z),
        ChangeMeasurementBasisPass(Basis.Z),
        ChangeControlledGateBasisPass(
            Basis.X, ScheduleConstant(1), ScheduleConstant(7)
        ),
    ],
)
