from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import stim

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.detectors.detector import Detector
from tqec.compile.observables.builder import Observable
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECException


@dataclass(frozen=True)
class DetectorAnnotation:
    """An annotation that should include all the necessary information to build a
    ``DETECTOR`` instruction."""

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

    @staticmethod
    def from_detector(
        detector: Detector, measurement_records: MeasurementRecordsMap
    ) -> DetectorAnnotation:
        """Create a :class:`DetectorAnnotation` from a detector and a list of
        measurement records."""
        return DetectorAnnotation(
            detector.coordinates,
            [measurement_records[m.qubit][m.offset] for m in detector.measurements],
        )


@dataclass
class LayerNodeAnnotations:
    circuit: ScheduledCircuit | None = None
    detectors: list[DetectorAnnotation] = field(default_factory=list)
    observables: list[Observable] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "circuit_str": (
                str(self.circuit.get_circuit()) if self.circuit is not None else None
            ),
            "detectors": self.detectors,
            "observables": self.observables,
        }


@dataclass
class LayerTreeAnnotations:
    qubit_map: QubitMap | None = None

    @property
    def has_qubit_map(self) -> bool:
        return self.qubit_map is not None

    def to_dict(self) -> dict[str, Any]:
        ret: dict[str, Any] = {"qubit_map": None}
        if self.qubit_map is not None:
            ret["qubit_map"] = {i: (q.x, q.y) for i, q in self.qubit_map.i2q.items()}
        return ret
