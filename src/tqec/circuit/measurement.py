"""Defines two classes to represent measurements in a quantum circuit.

This module defines :class:`Measurement` to represent a unique measurement in
a quantum circuit and :class:`RepeatedMeasurement` to represent a unique
measurement within a `REPEAT` instruction in a quantum circuit.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import stim
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import (
    is_multi_qubit_measurement_instruction,
    is_single_qubit_measurement_instruction,
)
from tqec.utils.position import Shift2D


class AbstractMeasurement(ABC):
    """Base class to represent a measurement."""

    @abstractmethod
    def offset_spatially_by(self, x: int, y: int) -> AbstractMeasurement:
        """Return a new instance offset by the provided spatial coordinates.

        Args:
            x: first spatial dimension offset.
            y: second spatial dimension offset.

        Returns:
            a new instance with the specified offset from ``self``.

        """

    @abstractmethod
    def offset_temporally_by(self, t: int) -> AbstractMeasurement:
        """Return a new instance offset by the provided temporal coordinates.

        Args:
            t: temporal offset.

        Returns:
            a new instance with the specified offset from ``self``.

        """

    @abstractmethod
    def __repr__(self) -> str:
        """Python magic method to represent an instance as a string."""

    @abstractmethod
    def map_qubit(self, qubit_map: Mapping[GridQubit, GridQubit]) -> AbstractMeasurement:
        """Return a copy of ``self`` with qubits mapped according to the provided``qubit_map``.

        The returned instance represents a measurement on the qubit obtained from ``self.qubit`` and
        the provided ``qubit_map``.

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
        TQECError: if the provided ``offset`` is not strictly negative.

    """

    qubit: GridQubit
    offset: int

    def __post_init__(self) -> None:
        if self.offset >= 0:
            raise TQECError("Measurement.offset should be negative.")

    @override
    def offset_spatially_by(self, x: int, y: int) -> Measurement:
        return Measurement(self.qubit + Shift2D(x, y), self.offset)

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

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the measurement.

        Returns:
            a dictionary with the keys ``qubit`` and ``offset`` and their
            corresponding values.

        """
        return {"qubit": [self.qubit.x, self.qubit.y], "offset": self.offset}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Measurement:
        """Return a measurement from its dictionary representation.

        Args:
            data: dictionary with the keys ``qubit`` and ``offset``.

        Returns:
            a new instance of :class:`Measurement` with the provided
            ``qubit`` and ``offset``.

        """
        qubit = GridQubit(data["qubit"][0], data["qubit"][1])
        offset = data["offset"]
        return Measurement(qubit, offset)


def get_measurements_from_circuit(circuit: stim.Circuit) -> list[Measurement]:
    """Get all the measurements found in the provided circuit.

    Args:
        circuit: circuit to extract measurements from.

    Raises:
        TQECError: if the provided circuit contains a ``REPEAT`` block.
        TQECError: if the provided circuit contains a multi-qubit measurement
            gate such as ``MXX`` or ``MPP``.
        TQECError: if the provided circuit contains a single-qubit
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
            raise TQECError(
                "Found a REPEAT block in get_measurements_from_circuit. This is not supported."
            )
        if is_multi_qubit_measurement_instruction(instruction):
            raise TQECError(
                f"Got a multi-qubit measurement instruction ({instruction.name}) "
                "but multi-qubit measurements are not supported yet."
            )
        if is_single_qubit_measurement_instruction(instruction):
            for (target,) in reversed(instruction.target_groups()):
                if not target.is_qubit_target:
                    raise TQECError(
                        "Found a measurement instruction with a target that is "
                        f"not a qubit target: {instruction}."
                    )
                qi: int = cast(int, target.qubit_value)
                qubit = qubit_map.i2q[qi]
                meas_index_on_qubit = num_measurements.get(qubit, 0) + 1
                num_measurements[qubit] = meas_index_on_qubit
                measurements_reverse_order.append(Measurement(qubit, -meas_index_on_qubit))
    return measurements_reverse_order[::-1]
