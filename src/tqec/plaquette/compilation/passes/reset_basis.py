from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
    ScheduleOffset,
)
from tqec.plaquette.enums import Basis


class ChangeResetBasisPass(ScheduledCircuitTransformationPass):
    """Change ``RX`` and ``RZ`` instructions to the provided basis."""

    def __init__(self, basis: Basis):
        ibasis = Basis.X if basis == Basis.Z else Basis.Z
        transformations = [
            ScheduledCircuitTransformation(
                f"R{ibasis.value.upper()}",
                {
                    ScheduleOffset(0): [InstructionCreator(f"R{basis.value.upper()}")],
                    ScheduleOffset(1): [InstructionCreator("H")],
                },
            )
        ]

        super().__init__(transformations)
