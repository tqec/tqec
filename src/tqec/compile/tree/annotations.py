from dataclasses import dataclass, field

import stim

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECException


@dataclass(frozen=True)
class DetectorAnnotation:
    """An annotation that should include all the necessary information to build a
    DETECTOR instruction.

    Todo:
        Will change according to the needs.
    """

    coordinates: StimCoordinates
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "DETECTOR",
            [stim.target_rec(offset) for offset in self.measurement_offsets],
            self.coordinates.to_stim_coordinates(),
        )


@dataclass(frozen=True)
class ObservableAnnotation:
    """An annotation that should include all the necessary information to build a
    OBSERVABLE_INCLUDE instruction.

    Todo:
        Will change according to the needs.
    """

    observable_index: int
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "OBSERVABLE_INCLUDE",
            [stim.target_rec(offset) for offset in self.measurement_offsets],
            [self.observable_index],
        )


@dataclass
class LayerNodeAnnotations:
    circuit: ScheduledCircuit | None = None
    detectors: list[DetectorAnnotation] = field(default_factory=list)
    observables: list[ObservableAnnotation] = field(default_factory=list)


@dataclass
class LayerTreeAnnotations:
    qubit_map: QubitMap | None = None

    @property
    def has_qubit_map(self) -> bool:
        return self.qubit_map is None
