from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
)
from tqec.plaquette.enums import ResetBasis


class ChangeResetBasisPass(ScheduledCircuitTransformationPass):
    def __init__(self, basis: ResetBasis):
        ibasis = ResetBasis.X if basis == ResetBasis.Z else ResetBasis.Z
        transformations = [
            ScheduledCircuitTransformation(
                f"R{ibasis.value.upper()}",
                {
                    0: [InstructionCreator(f"R{basis.value.upper()}", list)],
                    1: [InstructionCreator("H", list)],
                },
            )
        ]
        if basis == ResetBasis.X:
            transformations.append(
                ScheduledCircuitTransformation(
                    "R",
                    {
                        0: [InstructionCreator("RX", list)],
                        1: [InstructionCreator("H", list)],
                    },
                )
            )
        super().__init__(transformations)
