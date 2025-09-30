"""Defines :class:`.MeasurementRecordsMap` which is used to query measurement offsets in a circuit.

This module defines :class:`MeasurementRecordsMap`. This class implements the
necessary interface to register, modify and query measurement offsets from a
``stim.Circuit``.

"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy
import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import ScheduledCircuit
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import (
    is_multi_qubit_measurement_instruction,
    is_single_qubit_measurement_instruction,
)


@dataclass(frozen=True)
class MeasurementRecordsMap:
    """A mapping from measurements appearing in a circuit and their record offsets.

    This class stores record offsets which are, by essence, relative to a certain
    position in a circuit. This means that this class and the measurement offsets
    it stores are meaningless without knowledge about the circuit containing the
    represented measurements and the position(s) in the circuit at which the
    instance at hand is valid.

    Raises:
        TQECError: if at least one of the provided measurement record offsets
            is non-negative (``>=0``).
        TQECError: if, for any of the provided qubits, the provided offsets
            are not sorted.
        TQECError: if any measurement offset is duplicated.

    """

    mapping: dict[GridQubit, list[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        all_measurement_records_indices: list[int] = []
        for qubit, measurement_record_offsets in self.mapping.items():
            # Check that the provided measurement record offsets are negative.
            nonnegative_offsets = [offset for offset in measurement_record_offsets if offset >= 0]
            if nonnegative_offsets:
                raise TQECError(
                    "Invalid mapping from qubit offsets to measurement record "
                    f"offsets. Found positive offsets ({nonnegative_offsets}) for "
                    f"qubit {qubit}."
                )
            # Check that measurement record offsets are sorted
            if measurement_record_offsets != sorted(measurement_record_offsets):
                raise TQECError(
                    "Got measurement record offsets that are not in sorted "
                    f"order: {measurement_record_offsets}. This is not supported."
                )
            all_measurement_records_indices.extend(measurement_record_offsets)
        # Check that a given measurement record offset only appears once.
        deduplicated_indices = numpy.unique(all_measurement_records_indices)
        if len(deduplicated_indices) != len(all_measurement_records_indices):
            raise TQECError(
                "At least one measurement record offset has been found "
                "twice in the provided offsets."
            )

    @staticmethod
    def from_scheduled_circuit(circuit: ScheduledCircuit) -> MeasurementRecordsMap:
        """Build a :class:`MeasurementRecordsMap` from a scheduled circuit.

        Args:
            circuit: circuit containing the measurements to map.

        Raises:
            TQECError: if the provided ``circuit`` contains a ``REPEAT`` block.
            TQECError: if the provided ``circuit`` contains an unsupported
                measurement instruction. Currently, this method supports all
                single-qubit measurement instructions (see the value of
                ``SINGLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES``).
            TQECError: if one of the measurement counted in
                ``circuit.num_measurements`` was not processed (this should never
                raise, but the post-condition is easy to check so this method
                performs the check just in case).

        Returns:
            a :class:`MeasurementRecordsMap` linking measurements in the provided
            ``circuit`` to their offset.

        """
        return MeasurementRecordsMap.from_circuit(
            circuit.get_circuit(include_qubit_coords=False), circuit.qubit_map
        )

    @staticmethod
    def from_circuit(
        circuit: stim.Circuit, qubit_map: QubitMap | None = None
    ) -> MeasurementRecordsMap:
        """Build a :class:`MeasurementRecordsMap` from a circuit.

        Args:
            circuit: circuit containing the measurements to map.
            qubit_map: qubit map of the provided circuit. If ``None``, the
                qubit map is computed from the provided circuit. Default to
                ``None``.

        Raises:
            TQECError: if the provided ``circuit`` contains a ``REPEAT`` block.
            TQECError: if the provided ``circuit`` contains an unsupported
                measurement instruction. Currently, this method supports all
                single-qubit measurement instructions (see the value of
                ``SINGLE_QUBIT_MEASUREMENT_INSTRUCTION_NAMES``).
            TQECError: if one of the measurement counted in
                ``circuit.num_measurements`` was not processed (this should never
                raise, but the post-condition is easy to check so this method
                performs the check just in case).

        Returns:
            a :class:`MeasurementRecordsMap` linking measurements in the provided
            ``circuit`` to their offset.

        """
        # We iterate the circuit in forward order, which means that the first
        # measurement we will encounter will have a record offset of
        # `-circuit.num_measurements`. Iterating in this order also allows to
        # ensure by construction that the measurement record offsets will be in
        # sorted order.
        current_measurement_record = -circuit.num_measurements
        if qubit_map is None:
            qubit_map = QubitMap.from_circuit(circuit)
        measurement_records: dict[GridQubit, list[int]] = {}
        for instruction in circuit:
            if isinstance(instruction, stim.CircuitRepeatBlock):
                raise TQECError("Found a REPEAT instruction. This is not supported for the moment.")
            if is_multi_qubit_measurement_instruction(instruction):
                raise TQECError(f"Found a non-supported measurement instruction: {instruction}")
            if is_single_qubit_measurement_instruction(instruction):
                for (qi,) in instruction.target_groups():
                    qubit = qubit_map.i2q[qi.value]
                    measurement_records.setdefault(qubit, []).append(current_measurement_record)
                    current_measurement_record += 1
        if current_measurement_record != 0:
            raise TQECError(
                "Failed post-condition check. Expected a final measurement record of "
                f"-1 but got {current_measurement_record - 1}. Did we miss a "
                f"measurement? Circuit:\n{circuit}"
            )
        return MeasurementRecordsMap(measurement_records)

    # Explicitly returns a Sequence to show that the returned value is read-only.
    def __getitem__(self, qubit: GridQubit) -> Sequence[int]:
        return self.mapping[qubit]

    def __contains__(self, qubit: GridQubit) -> bool:
        return qubit in self.mapping

    def with_added_measurements(
        self, mrecords_map: MeasurementRecordsMap, repetitions: int = 1
    ) -> MeasurementRecordsMap:
        """Build a new instance with measurements from ``self`` and ``mrecords_map``.

        Measurements from ``self`` appear before measurements from the provided ``mrecords_map``.

        Args:
            mrecords_map: records of measurements happening after the measurements
                represented by ``self``.
            repetitions: number of time the measurements from ``mrecords_map`` are
                repeated. Default to 1.

        Returns:
            a new instance containing valid offsets for each measurement in ``self``
            and ``mrecords_map``.

        """
        num_measurements_without_repetition = sum(
            len(offsets) for offsets in mrecords_map.mapping.values()
        )
        num_added_measurements = repetitions * num_measurements_without_repetition
        records = {
            q: [o - num_added_measurements for o in offsets] for q, offsets in self.mapping.items()
        }
        for q, offsets in mrecords_map.mapping.items():
            record = records.setdefault(q, [])
            for i in range(repetitions - 1, -1, -1):
                record.extend([o - i * num_measurements_without_repetition for o in offsets])
        return MeasurementRecordsMap(records)
