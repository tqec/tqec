from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
    ScheduleOffset,
)
from tqec.utils.enums import Basis


class ChangeMeasurementBasisPass(ScheduledCircuitTransformationPass):
    def __init__(self, basis: Basis):
        """Change ``MX`` and ``MZ`` instructions to the provided ``basis``."""
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
