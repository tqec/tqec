"""Defines two classes to represent measurements in a quantum circuit.

This module defines :class:`Measurement` to represent a unique measurement in
a quantum circuit and :class:`RepeatedMeasurement` to represent a unique
measurement within a `REPEAT` instruction in a quantum circuit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, cast

import stim
from typing_extensions import override

from tqec.circuit.instructions import (
    is_multi_qubit_measurement_instruction,
    is_single_qubit_measurement_instruction,
)
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.exceptions import TQECException
from tqec.interval import Interval, Rplus_interval
from tqec.position import Displacement


class AbstractMeasurement(ABC):
    """Base class to represent a measurement."""

    @abstractmethod
    def offset_spatially_by(self, x: int, y: int) -> AbstractMeasurement:
        """Returns a new instance offset by the provided spatial coordinates.

        Args:
            x: first spatial dimension offset.
            y: second spatial dimension offset.

        Returns:
            a new instance with the specified offset from ``self``.
        """

    @abstractmethod
    def offset_temporally_by(self, t: int) -> AbstractMeasurement:
        """Returns a new instance offset by the provided temporal coordinates.

        Args:
            t: temporal offset.

        Returns:
            a new instance with the specified offset from ``self``.
        """

    @abstractmethod
    def __repr__(self) -> str:
        """Python magic method to represent an instance as a string."""

    @abstractmethod
    def map_qubit(
        self, qubit_map: Mapping[GridQubit, GridQubit]
    ) -> AbstractMeasurement:
        """Returns a new instance representing a measurement on the qubit
        obtained from ``self.qubit`` and the provided ``qubit_map``.

        Args:
            qubit_map: a correspondence map for qubits.

        Returns:
            a new measurement instance with the mapped qubit.
        """


@dataclass(frozen=True)
class Measurement(AbstractMeasurement):
    """A unique representation for each measurement in a quantum circuit.

    This class aims at being able to represent measurements in a quantum circuit
    in a unique and easily usable way.

    Note:
        This is not a global representation as the ``offset`` is always
        relative to the end of the quantum circuit considered.

    Attributes:
        qubit: qubit on which the represented measurement is performed.
        offset: negative offset representing the number of measurements
            performed on the provided qubit after the represented measurement.
            A value of ``-1`` means that the represented measurement is the
            last one applied on ``qubit``.

    Raises:
        TQECException: if the provided ``offset`` is not strictly negative.
    """

    qubit: GridQubit
    offset: int

    def __post_init__(self) -> None:
        if self.offset >= 0:
            raise TQECException("Measurement.offset should be negative.")

    @override
    def offset_spatially_by(self, x: int, y: int) -> Measurement:
        return Measurement(self.qubit + Displacement(x, y), self.offset)

    @override
    def offset_temporally_by(self, t: int) -> Measurement:
        return Measurement(self.qubit, self.offset + t)

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.qubit}, {self.offset})"

    def __str__(self) -> str:
        return f"M[{self.qubit},{self.offset}]"

    @override
    def map_qubit(self, qubit_map: Mapping[GridQubit, GridQubit]) -> Measurement:
        return Measurement(qubit_map[self.qubit], self.offset)


@dataclass(frozen=True)
class RepeatedMeasurement(AbstractMeasurement):
    """A unique representation for a repeated measurement in a quantum circuit.

    This class aims at being able to represent a repeated measurement in a
    quantum circuit in a unique and easily usable way.
    Repeated measurements can be found when a ``stim.CircuitRepeatBlock``
    contains measurements.

    Note:
        This is not a global representation as the ``offsets`` is always
        relative to the end of the quantum circuit considered.

    Attributes:
        qubit: qubit on which the represented repeated measurement is performed.
        offsets: an interval only containing negative offsets representing the
            number of measurements performed on the provided qubit after the
            represented measurement.
            A value of ``-1`` means that the represented measurement is the
            last one applied on ``qubit``.

    Raises:
        TQECException: if the provided ``offset`` contains positive entries.
    """

    qubit: GridQubit
    offsets: Interval

    def __post_init__(self) -> None:
        if not self.offsets.intersection(Rplus_interval).is_empty():
            raise TQECException(
                "Measurement.offsets should be an Interval "
                "containing only strictly negative values."
            )

    @override
    def offset_spatially_by(self, x: int, y: int) -> RepeatedMeasurement:
        return RepeatedMeasurement(self.qubit + Displacement(x, y), self.offsets)

    @override
    def offset_temporally_by(self, t: int) -> RepeatedMeasurement:
        return RepeatedMeasurement(self.qubit, self.offsets + t)

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.qubit}, {self.offsets})"

    @override
    def map_qubit(
        self, qubit_map: Mapping[GridQubit, GridQubit]
    ) -> RepeatedMeasurement:
        return RepeatedMeasurement(qubit_map[self.qubit], self.offsets)

    def measurements(self) -> list[Measurement]:
        return [
            Measurement(self.qubit, offset) for offset in self.offsets.iter_integers()
        ]


def get_measurements_from_circuit(circuit: stim.Circuit) -> list[Measurement]:
    """Get all the measurements found in the provided circuit.

    Args:
        circuit: circuit to extract measurements from.

    Raises:
        TQECException: if the provided circuit contains a ``REPEAT`` block.
        TQECException: if the provided circuit contains a multi-qubit measurement
            gate such as ``MXX`` or ``MPP``.
        TQECException: if the provided circuit contains a single-qubit
            measurement gate with a non-qubit target.

    Returns:
        all the measurements present in the provided ``circuit``, in their order
        of appearance (so in increasing order of measurement record offsets).
    """
    qubit_map = QubitMap.from_circuit(circuit)
    num_measurements: dict[GridQubit, int] = {}
    measurements_reverse_order: list[Measurement] = []
    for instruction in reversed(circuit):
        if isinstance(instruction, stim.CircuitRepeatBlock):
            raise TQECException(
                "Found a REPEAT block in get_measurements_from_circuit. This "
                "is not supported."
            )
        if is_multi_qubit_measurement_instruction(instruction):
            raise TQECException(
                f"Got a multi-qubit measurement instruction ({instruction.name}) "
                "but multi-qubit measurements are not supported yet."
            )
        if is_single_qubit_measurement_instruction(instruction):
            for (target,) in reversed(instruction.target_groups()):
                if not target.is_qubit_target:
                    raise TQECException(
                        "Found a measurement instruction with a target that is "
                        f"not a qubit target: {instruction}."
                    )
                qi: int = cast(int, target.qubit_value)
                qubit = qubit_map.i2q[qi]
                meas_index_on_qubit = num_measurements.get(qubit, 0) + 1
                num_measurements[qubit] = meas_index_on_qubit
                measurements_reverse_order.append(
                    Measurement(qubit, -meas_index_on_qubit)
                )
    return measurements_reverse_order[::-1]
