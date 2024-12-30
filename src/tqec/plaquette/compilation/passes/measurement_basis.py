from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
    ScheduleOffset,
)
from tqec.plaquette.enums import MeasurementBasis


class ChangeMeasurementBasisPass(ScheduledCircuitTransformationPass):
    def __init__(self, basis: MeasurementBasis):
        ibasis = (
            MeasurementBasis.X if basis == MeasurementBasis.Z else MeasurementBasis.Z
        )
        transformations = [
            ScheduledCircuitTransformation(
                f"M{ibasis.value.upper()}",
                {
                    ScheduleOffset(-1): [InstructionCreator("H", list)],
                    ScheduleOffset(0): [
                        InstructionCreator(f"M{basis.value.upper()}", list)
                    ],
                },
            )
        ]
        if basis == MeasurementBasis.X:
            transformations.append(
                ScheduledCircuitTransformation(
                    "M",
                    {
                        ScheduleOffset(-1): [InstructionCreator("H", list)],
                        ScheduleOffset(0): [InstructionCreator("MX", list)],
                    },
                )
            )
        super().__init__(transformations)
