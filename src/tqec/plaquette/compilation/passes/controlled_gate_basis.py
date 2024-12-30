from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
    ScheduleFunction,
    ScheduleOffset,
)
from tqec.plaquette.compilation.passes.transformer.simplifiers import (
    SelfInverseGateSimplification,
)
from tqec.plaquette.enums import Basis


class ChangeControlledGateBasisPass(ScheduledCircuitTransformationPass):
    def __init__(
        self, basis: Basis, bcsched1: ScheduleFunction, bcsched2: ScheduleFunction
    ) -> None:
        ibasis = Basis.X if basis == Basis.Z else Basis.Z
        transformations = [
            ScheduledCircuitTransformation(
                f"C{ibasis.value.upper()}",
                {
                    ScheduleOffset(0): [InstructionCreator(f"C{basis.value.upper()}")],
                    bcsched1: [InstructionCreator("H", lambda trgts: trgts[1::2])],
                    bcsched2: [InstructionCreator("H", lambda trgts: trgts[1::2])],
                },
                instruction_simplifier=SelfInverseGateSimplification(),
            )
        ]
        super().__init__(transformations)
