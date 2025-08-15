"""Defines :class:`Detector` to represent detectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import stim

from tqec.circuit.measurement import Measurement
from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECError


@dataclass(frozen=True)
class Detector:
    """Represent a detector as a set of measurements and optional coordinates."""

    measurements: frozenset[Measurement]
    coordinates: StimCoordinates

    def __post_init__(self) -> None:
        if not self.measurements:
            raise TQECError("Trying to create a detector without any measurement.")

    def __hash__(self) -> int:
        return hash(self.measurements)

    def __eq__(self, rhs: object) -> bool:
        return (
            isinstance(rhs, Detector)
            and self.measurements == rhs.measurements
            and self.coordinates == rhs.coordinates
        )

    def __str__(self) -> str:
        measurements_str = "{" + ",".join(map(str, self.measurements)) + "}"
        return f"D{self.coordinates}{measurements_str}"

    def to_instruction(
        self, measurement_records_map: MeasurementRecordsMap
    ) -> stim.CircuitInstruction:
        """Return the ``stim.CircuitInstruction`` instance representing the detector in ``self``.

        Args:
            measurement_records_map: a map from qubits and qubit-local
                measurement offsets to global measurement offsets.

        Raises:
            TQECError: if any of the measurements stored in `self` is
                performed on a qubit that is not in the provided
                `measurement_records_map`.
            KeyError: if any of the qubit-local measurement offsets stored in
                `self` is not present in the provided `measurement_records_map`.

        Returns:
            the `DETECTOR` instruction representing `self`. Note that the
            instruction has the same validity region as the provided
            `measurement_records_map`.

        """
        measurement_records: list[stim.GateTarget] = []
        for measurement in self.measurements:
            if measurement.qubit not in measurement_records_map:
                raise TQECError(
                    f"Trying to get measurement record for {measurement.qubit} "
                    "but qubit is not in the measurement record map."
                )
            measurement_records.append(
                stim.target_rec(measurement_records_map[measurement.qubit][measurement.offset])
            )
        measurement_records.sort(key=lambda mr: mr.value, reverse=True)
        return stim.CircuitInstruction(
            "DETECTOR", measurement_records, self.coordinates.to_stim_coordinates()
        )

    def offset_spatially_by(self, x: int, y: int) -> Detector:
        """Offset the coordinates and all the qubits involved in `self`.

        Args:
            x: offset in the first spatial dimension.
            y: offset in the second spatial dimension.

        Returns:
            a new detector that has been spatially offset by the provided `x`
            and `y` offsets.

        """
        return Detector(
            frozenset(m.offset_spatially_by(x, y) for m in self.measurements),
            self.coordinates.offset_spatially_by(x, y),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the detector.

        Returns:
            a dictionary with the keys ``measurements`` and ``coordinates`` and
            their corresponding values.

        """
        return {
            "measurements": [m.to_dict() for m in self.measurements],
            "coordinates": self.coordinates.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Detector:
        """Return a detector from its dictionary representation.

        Args:
            data: dictionary with the keys ``measurements`` and ``coordinates``.

        Returns:
            a new instance of :class:`Detector` with the provided
            ``measurements`` and ``coordinates``.

        """
        measurements = frozenset(Measurement.from_dict(m) for m in data["measurements"])
        coordinates = StimCoordinates.from_dict(data["coordinates"])
        return Detector(measurements, coordinates)
