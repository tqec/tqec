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


def remove_non_deterministic_detectors(circuit: stim.Circuit) -> stim.Circuit:
    """Remove ``DETECTOR`` instructions that are not deterministic in ``circuit``.

    Detectors are automatically computed from a spatially and temporally local
    window (see :mod:`tqec.compile.detectors.compute`) that is not guaranteed
    to contain every operation that is relevant to decide whether a candidate
    detector is deterministic or not. In some situations (typically, at the
    boundary between two spatial-junction corners that are stacked in time
    without a pipe connecting them, see
    `#1062 <https://github.com/tqec/tqec/issues/1062>`_), the local window
    used to compute a detector misses a reset or a measurement that is
    performed just outside of it, leading to a detector that is invalid (i.e.,
    not a deterministic function of the measurement outcomes it is built
    from) being inserted in the final, global circuit.

    This function is a defensive, **exact** (i.e., not based on sampling)
    check performed on the fully assembled, noiseless circuit. It relies on
    :meth:`stim.Circuit.detector_error_model` with ``allow_gauge_detectors``
    set to ``True``: in a noiseless circuit, any resulting error mechanism
    with a probability of exactly ``0.5`` corresponds to a set of detectors
    that anti-commute with a reset or measurement, i.e., that are not
    deterministic. Note that, because the circuit checked here has not been
    through any noise model yet, any such error mechanism can only originate
    from a non-deterministic detector and not from an actual noise channel.

    Args:
        circuit: a fully assembled, noiseless ``stim.Circuit`` that might
            contain non-deterministic ``DETECTOR`` instructions.

    Returns:
        a copy of ``circuit`` with every non-deterministic ``DETECTOR``
        instruction removed. If ``circuit`` does not contain any
        non-deterministic detector, ``circuit`` is returned unchanged (in
        particular, ``REPEAT`` blocks are preserved in that common case).
        If ``circuit`` contains at least one ``REPEAT`` block *and* at least
        one non-deterministic detector, the returned circuit is fully
        flattened (see :meth:`stim.Circuit.flattened`): mapping detector
        indices back to the ``DETECTOR`` instruction(s) responsible for them
        is ambiguous otherwise, as the same instruction inside a ``REPEAT``
        block can be responsible for several detectors (one per loop
        iteration) that are not necessarily all non-deterministic.

    """
    # First, a cheap check: analyze `circuit` with `flatten_loops=False` (the
    # `stim` default), which lets `stim` compact `REPEAT` blocks into a
    # periodic steady state instead of fully unrolling them. This is enough
    # to detect *whether* a non-deterministic detector exists, and is
    # considerably cheaper on the common, no-issue path for circuits with
    # many rounds (e.g. memory experiments), which is by far the most common
    # case in practice.
    non_deterministic_detector_indices = _non_deterministic_detector_indices(
        circuit, flatten_loops=False
    )
    if not non_deterministic_detector_indices:
        return circuit

    # A non-deterministic detector was found. If `circuit` contains a
    # `REPEAT` block, the indices computed above are not guaranteed to
    # unambiguously identify which `DETECTOR` instruction(s) to remove: the
    # same instruction inside a loop can be responsible for several
    # detectors (one per loop iteration) that are not necessarily all
    # non-deterministic. Only in that (now rare) case, pay the cost of a
    # fully unrolled analysis (`flatten_loops=True`) and flatten `circuit`
    # itself so that detector indices map one-to-one onto `DETECTOR`
    # instructions.
    if any(instruction.name == "REPEAT" for instruction in circuit):
        circuit = circuit.flattened()
        non_deterministic_detector_indices = _non_deterministic_detector_indices(
            circuit, flatten_loops=True
        )

    filtered_circuit = stim.Circuit()
    detector_index = -1
    for instruction in circuit:
        if isinstance(instruction, stim.CircuitInstruction) and instruction.name == "DETECTOR":
            detector_index += 1
            if detector_index in non_deterministic_detector_indices:
                continue
        filtered_circuit.append(instruction)
    return filtered_circuit


def _non_deterministic_detector_indices(
    circuit: stim.Circuit, *, flatten_loops: bool
) -> frozenset[int]:
    """Return the indices of the detectors in ``circuit`` that are not deterministic.

    See :func:`remove_non_deterministic_detectors` for more context. With
    ``flatten_loops=False``, this only reliably answers *whether* a
    non-deterministic detector exists (as a non-empty result); the specific
    indices are only unambiguous indices into the fully flattened sequence of
    ``DETECTOR`` instructions when ``flatten_loops=True`` and ``circuit`` does
    not contain a ``REPEAT`` block, or has already been flattened (see
    :meth:`stim.Circuit.flattened`).

    """
    dem = circuit.detector_error_model(
        decompose_errors=False,
        allow_gauge_detectors=True,
        flatten_loops=flatten_loops,
    )
    indices: set[int] = set()
    for instruction in dem:
        # `flatten_loops=True` guarantees that `dem` does not contain any
        # `stim.DemRepeatBlock`, but that is not statically known, hence the
        # `isinstance` check.
        if not isinstance(instruction, stim.DemInstruction) or instruction.type != "error":
            continue
        (probability,) = instruction.args_copy()
        if abs(probability - 0.5) > 1e-9:
            continue
        indices.update(
            target.val
            for target in instruction.targets_copy()
            if isinstance(target, stim.DemTarget) and target.is_relative_detector_id()
        )
    return frozenset(indices)
