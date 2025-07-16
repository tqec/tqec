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
from tqec.utils.enums import Basis


class ChangeControlledGateBasisPass(ScheduledCircuitTransformationPass):
    def __init__(
        self, basis: Basis, bcsched1: ScheduleFunction, bcsched2: ScheduleFunction
    ) -> None:
        """Change ``CX`` or ``CZ`` gates to the provided basis.

        Args:
            basis: the target basis. If ``X``, all ``CZ`` gates will be changed
                to ``CX``. If ``Z``, all ``CX`` gates will be changed to ``CZ``.
            bcsched1: basis change schedule 1, a description of the schedule at
                which the potential first basis change (``H`` gate applied
                **before** the controlled gate) should be inserted.
            bcsched2: basis change schedule 2, a description of the schedule at
                which the potential second basis change (``H`` gate applied
                **after** the controlled gate) should be inserted.

        """
        ibasis = Basis.X if basis == Basis.Z else Basis.Z
        transformations = [
            ScheduledCircuitTransformation(
                f"C{ibasis.value.upper()}",
                {
                    ScheduleOffset(0): [InstructionCreator(f"C{basis.value.upper()}")],
                    bcsched1: [InstructionCreator("H", lambda trgts: trgts[1::2])],
                    bcsched2: [InstructionCreator("H", lambda trgts: trgts[1::2])],
                },
                instruction_simplifier=SelfInverseGateSimplification("H"),
            )
        ]
        super().__init__(transformations)
