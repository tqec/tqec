from tqec.plaquette.compilation.passes.transformer import (
    InstructionCreator,
    ScheduledCircuitTransformation,
    ScheduledCircuitTransformationPass,
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
                    -1: [InstructionCreator("H", list)],
                    0: [InstructionCreator(f"M{basis.value.upper()}", list)],
                },
            )
        ]
        if basis == MeasurementBasis.X:
            transformations.append(
                ScheduledCircuitTransformation(
                    "M",
                    {
                        -1: [InstructionCreator("H", list)],
                        0: [InstructionCreator("MX", list)],
                    },
                )
            )
        super().__init__(transformations)
