"""Defines :class:`~tqec.circuit.qubit.GridQubit` and helper functions to manage qubits.

This module defines a central class to represent a qubit placed on a
2-dimensional grid, :class:`GridQubit`, and a few functions to extract
qubit-related information from ``stim.Circuit`` instances.

"""

from __future__ import annotations

from collections import defaultdict
from typing import cast

import stim

from tqec.utils.coordinates import StimCoordinates
from tqec.utils.position import PhysicalQubitPosition2D, Shift2D


class GridQubit:
    def __init__(self, x: int, y: int) -> None:
        """Represent a qubit placed on a 2-dimensional grid.

        Args:
            x: first coordinate.
            y: second coordinate.

        """
        self._x = x
        self._y = y

    @property
    def x(self) -> int:
        """Coordinate of the qubit in the first spatial dimension."""
        return self._x

    @property
    def y(self) -> int:
        """Coordinate of the qubit in the second spatial dimension."""
        return self._y

    def to_qubit_coords_instruction(self, index: int) -> stim.CircuitInstruction:
        """Return the ``QUBIT_COORDS`` instruction defining ``self`` in a ``stim.Circuit``."""
        return stim.CircuitInstruction(
            "QUBIT_COORDS",
            [index],
            StimCoordinates(self.x, self.y).to_stim_coordinates(),
        )

    def __add__(self, other: GridQubit | PhysicalQubitPosition2D | Shift2D) -> GridQubit:
        return GridQubit(self.x + other.x, self.y + other.y)

    def __sub__(self, other: GridQubit | PhysicalQubitPosition2D | Shift2D) -> GridQubit:
        return GridQubit(self.x - other.x, self.y - other.y)

    def __mul__(self, other: int) -> GridQubit:
        return GridQubit(other * self.x, other * self.y)

    def __rmul__(self, other: int) -> GridQubit:
        return GridQubit(other * self.x, other * self.y)

    def __hash__(self) -> int:
        return hash((self._x, self._y))

    def __eq__(self, value: object) -> bool:
        return isinstance(value, GridQubit) and self._x == value._x and self._y == value._y

    def __lt__(self, other: GridQubit) -> bool:
        return (self._x, self._y) < (other._x, other._y)

    def __repr__(self) -> str:
        return f"GridQubit({self.x}, {self.y})"

    def __str__(self) -> str:
        return f"Q[{self.x}, {self.y}]"

    def to_dict(self) -> dict[str, int]:
        """Return a dictionary representation of the qubit.

        Returns:
            a dictionary with the keys ``x`` and ``y`` and their
            corresponding values.

        """
        return {"x": self.x, "y": self.y}

    @staticmethod
    def from_dict(data: dict[str, int]) -> GridQubit:
        """Return a qubit from its dictionary representation.

        Args:
            data: dictionary with the keys ``x`` and ``y``.

        Returns:
            a new instance of :class:`GridQubit` with the provided
            ``x`` and ``y``.

        """
        return GridQubit(data["x"], data["y"])


"""Names of the `stim` instructions that are considered as annotations."""
ANNOTATION_INSTRUCTIONS: frozenset[str] = frozenset(
    [
        # Noise channels
        "CORRELATED_ERROR",
        "DEPOLARIZE1",
        "DEPOLARIZE2",
        "E",
        "ELSE_CORRELATED_ERROR",
        "HERALDED_ERASE",
        "HERALDED_PAULI_CHANNEL_1",
        "PAULI_CHANNEL_1",
        "PAULI_CHANNEL_2",
        "X_ERROR",
        "Y_ERROR",
        "Z_ERROR",
        # Annotations
        "DETECTOR",
        "MPAD",
        "OBSERVABLE_INCLUDE",
        "QUBIT_COORDS",
        "SHIFT_COORDS",
        "TICK",
    ]
)


def count_qubit_accesses(circuit: stim.Circuit) -> dict[int, int]:
    """Count the number of times a given qubit is used by an instruction that is not an annotation.

    Note:
        If a ``REPEAT`` instruction is found, each qubit access within the
        repeated block will be multiplied by the number of time the block is
        repeated.

    Args:
        circuit: circuit containing the gates.

    Returns:
        a mapping from qubit indices (as keys) to the number of non-annotation
        instructions that have this qubit index as target (as values).

    """
    counter: defaultdict[int, int] = defaultdict(int)
    for instruction in circuit:
        if isinstance(instruction, stim.CircuitRepeatBlock):
            for qi, count in count_qubit_accesses(instruction.body_copy()).items():
                counter[qi] += count * instruction.repeat_count
        else:
            if instruction.name in ANNOTATION_INSTRUCTIONS:
                continue
            for target in instruction.targets_copy():
                # Ignore targets that are not qubit targets.
                if not target.is_qubit_target:
                    continue
                qi = cast(int, target.qubit_value)
                counter[qi] += 1
    return counter


def get_used_qubit_indices(circuit: stim.Circuit) -> set[int]:
    """Return the indices of qubits that are used by at least one non-annotation instruction.

    Args:
        circuit: circuit containing the gates.

    Returns:
        the set of qubit indices that are used by at least one non-annotation
        instruction.

    """
    return set(count_qubit_accesses(circuit).keys())
