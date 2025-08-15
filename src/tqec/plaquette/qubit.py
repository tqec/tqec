from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.plaquette.enums import PlaquetteSide
from tqec.utils.enums import Orientation


@dataclass(frozen=True)
class PlaquetteQubits:
    data_qubits: list[GridQubit]
    syndrome_qubits: list[GridQubit]

    def __iter__(self) -> Iterator[GridQubit]:
        yield from self.data_qubits
        yield from self.syndrome_qubits

    @property
    def all_qubits(self) -> list[GridQubit]:
        """Return all the qubits represented by ``self``."""
        return list(self)

    def get_edge_qubits(
        self,
        orientation: Orientation = Orientation.HORIZONTAL,
    ) -> list[GridQubit]:
        """Return the data qubits on the edge of the plaquette.

        By convention, the edge is the one with the highest index in the relevant axis.

        Args:
            orientation (TemplateOrientation, optional): Whether to use horizontal or
                vertical orientation as the axis. Defaults to horizontal.

        Returns:
            The qubits on the edge of the plaquette.

        """

        def _get_relevant_value(qubit: GridQubit) -> int:
            return qubit.y if orientation == Orientation.HORIZONTAL else qubit.x

        max_index = max(_get_relevant_value(q) for q in self.data_qubits)
        return [qubit for qubit in self.data_qubits if (_get_relevant_value(qubit) == max_index)]

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
        return hash((tuple(self.syndrome_qubits), tuple(self.data_qubits)))  # pragma: no cover

    def __eq__(self, rhs: object) -> bool:
        return (
            isinstance(rhs, PlaquetteQubits)
            and self.data_qubits == rhs.data_qubits
            and self.syndrome_qubits == rhs.syndrome_qubits
        )

    @property
    def data_qubits_indices(self) -> Iterator[int]:
        """Return an iterator over the index of each data-qubit."""
        yield from range(len(self.data_qubits))

    @property
    def syndrome_qubits_indices(self) -> Iterator[int]:
        """Return an iterator over the index of each syndrome-qubit."""
        yield from (i + len(self.data_qubits) for i in range(len(self.syndrome_qubits)))

    @property
    def data_qubits_with_indices(self) -> Iterator[tuple[int, GridQubit]]:
        """Return an iterator over each data-qubit and their indices."""
        yield from ((i, q) for i, q in zip(self.data_qubits_indices, self.data_qubits))

    @property
    def syndrome_qubits_with_indices(self) -> Iterator[tuple[int, GridQubit]]:
        """Return an iterator over each syndrome-qubit and their indices."""
        yield from ((i, q) for i, q in zip(self.syndrome_qubits_indices, self.syndrome_qubits))

    @property
    def qubit_map(self) -> QubitMap:
        """Return the qubit map representing ``self``."""
        return QubitMap(
            dict(self.data_qubits_with_indices) | dict(self.syndrome_qubits_with_indices)
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the plaquette qubits.

        Returns:
            a dictionary with the keys ``data_qubits`` and ``syndrome_qubits`` and
            their corresponding values.

        """
        return {
            "data_qubits": [q.to_dict() for q in self.data_qubits],
            "syndrome_qubits": [q.to_dict() for q in self.syndrome_qubits],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PlaquetteQubits:
        """Return a plaquette qubits from its dictionary representation.

        Args:
            data: dictionary with the keys ``data_qubits`` and
                ``syndrome_qubits``.

        Returns:
            a new instance of :class:`PlaquetteQubits` with the provided
            ``data_qubits`` and ``syndrome_qubits``.

        """
        data_qubits = [GridQubit.from_dict(q) for q in data["data_qubits"]]
        syndrome_qubits = [GridQubit.from_dict(q) for q in data["syndrome_qubits"]]
        return PlaquetteQubits(data_qubits, syndrome_qubits)


class SquarePlaquetteQubits(PlaquetteQubits):
    def __init__(self) -> None:
        """Represent the qubits used by a regular square plaquette."""
        super().__init__(
            # Order is important here! Top-left, top-right, bottom-left,
            # bottom-right.
            [GridQubit(-1, -1), GridQubit(1, -1), GridQubit(-1, 1), GridQubit(1, 1)],
            [GridQubit(0, 0)],
        )
