from __future__ import annotations

import typing as ty
from dataclasses import dataclass

from tqec.circuit.qubit import GridQubit
from tqec.enums import Orientation
from tqec.plaquette.enums import PlaquetteSide


@dataclass(frozen=True)
class PlaquetteQubits:
    data_qubits: list[GridQubit]
    syndrome_qubits: list[GridQubit]

    def __iter__(self) -> ty.Iterator[GridQubit]:
        yield from self.data_qubits
        yield from self.syndrome_qubits

    @property
    def all_qubits(self) -> list[GridQubit]:
        return list(self)

    def get_edge_qubits(
        self,
        orientation: Orientation = Orientation.HORIZONTAL,
    ) -> list[GridQubit]:
        """Return the data qubits on the edge of the plaquette. By convention,
        the edge is the one with the highest index in the relevant axis.

        Args:
            orientation (TemplateOrientation, optional): Whether to use horizontal or
                vertical orientation as the axis. Defaults to horizontal.
        Returns:
            The qubits on the edge of the plaquette.
        """

        def _get_relevant_value(qubit: GridQubit) -> int:
            return qubit.y if orientation == Orientation.HORIZONTAL else qubit.x

        max_index = max(_get_relevant_value(q) for q in self.data_qubits)
        return [
            qubit
            for qubit in self.data_qubits
            if (_get_relevant_value(qubit) == max_index)
        ]

    def get_qubits_on_side(self, side: PlaquetteSide) -> list[GridQubit]:
        """Return the qubits one the provided side of the instance.

        A qubit is on the left-side if there is no other qubit in the instance
        with a strictly lower x-coordinate value. Similarly, a qubit is on the
        right-side if there is no other qubit in the instance with a strictly
        greater x-coordinate value. Up and down are about the y-coordinate.

        Args:
            side: the side to find qubits on.
        Returns:
            The qubits on the edge of the plaquette.
        """
        if side == PlaquetteSide.LEFT:
            min_x = min(q.x for q in self)
            return [q for q in self if q.x == min_x]
        elif side == PlaquetteSide.RIGHT:
            max_x = max(q.x for q in self)
            return [q for q in self if q.x == max_x]
        elif side == PlaquetteSide.UP:
            min_y = min(q.y for q in self)
            return [q for q in self if q.y == min_y]
        else:  # if orientation == PlaquetteSide.DOWN:
            max_y = max(q.y for q in self)
            return [q for q in self if q.y == max_y]

    def __hash__(self) -> int:
        return hash((tuple(self.syndrome_qubits), tuple(self.data_qubits)))

    def __eq__(self, rhs: object) -> bool:
        return (
            isinstance(rhs, PlaquetteQubits)
            and self.data_qubits == rhs.data_qubits
            and self.syndrome_qubits == rhs.syndrome_qubits
        )


class SquarePlaquetteQubits(PlaquetteQubits):
    def __init__(self) -> None:
        super().__init__(
            [GridQubit(-1, -1), GridQubit(1, -1), GridQubit(-1, 1), GridQubit(1, 1)],
            [GridQubit(0, 0)],
        )
