from tqec.enums import Basis
from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
    ScheduleOffset,
)


class ChangeMeasurementBasisPass(ScheduledCircuitTransformationPass):
    """Change ``MX`` and ``MZ`` instructions to the provided basis."""

    def __init__(self, basis: Basis):
        ibasis = Basis.X if basis == Basis.Z else Basis.Z
        transformations = [
            ScheduledCircuitTransformation(
                f"M{ibasis.value.upper()}",
                {
                    ScheduleOffset(-1): [InstructionCreator("H")],
                    ScheduleOffset(0): [InstructionCreator(f"M{basis.value.upper()}")],
                },
            )
        ]

        super().__init__(transformations)
