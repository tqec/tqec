"""Defines core data-structures to handle the mapping between qubit coordinates and qubit indices.

A bijection from qubit coordinates to qubit indices is represented by
:class:`QubitMap` defined in this module.

This bijection can be obtained from a ``stim.Circuit`` instance by using
:func:`get_qubit_map`.

"""

from __future__ import annotations

import functools
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import numpy
import stim

from tqec.circuit.qubit import GridQubit
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import round_or_fail


@dataclass(frozen=True)
class QubitMap:
    """Represent a bijection between :class:`~tqec.circuit.qubit.GridQubit` instances and indices.

    This class aims at representing a bidirectional mapping (hence the
    "bijection") between qubits and their associated indices.

    Raises:
        TQECError: if the provided mapping from indices to qubits is not a
            bijection (i.e., if at least to values represent the same qubit).

    """

    i2q: dict[int, GridQubit] = field(default_factory=dict)

    def __post_init__(self) -> None:
        qubit_counter = Counter(self.i2q.values())
        if len(qubit_counter) != len(self.i2q):
            duplicated_qubits = frozenset(q for q in qubit_counter if qubit_counter[q] > 1)
            raise TQECError(f"Found qubit(s) with more than one index: {duplicated_qubits}.")

    @staticmethod
    def from_qubits(qubits: Iterable[GridQubit]) -> QubitMap:
        """Create a qubit map from the provided ``qubits``.

        Qubit indices are associated in the order in which ``qubits`` are provided: the first qubit
        will have index ``0``, the second index ``1`` and so on.
        """
        return QubitMap(dict(enumerate(qubits)))

    @staticmethod
    def from_circuit(circuit: stim.Circuit) -> QubitMap:
        """Return a qubit map from the qubit coordinates at the end of the provided ``circuit``.

        Warning:
            This function, just like
            `stim.Circuit.get_final_qubit_coordinates <https://github.com/quantumlib/Stim/blob/main/doc/python_api_reference_vDev.md#stim.Circuit.get_final_qubit_coordinates>`_,
            returns the qubit coordinates **at the end** of the provided ``circuit``.

        Args:
            circuit: instance to get qubit coordinates from.

        Raises:
            TQECError: if any of the final qubits is not defined with exactly 2
                coordinates (we only consider qubits on a 2-dimensional grid).

        Returns:
            a mapping from qubit indices (keys) to qubit coordinates (values).

        """
        return get_qubit_map(circuit)

    @functools.cached_property
    def q2i(self) -> dict[GridQubit, int]:
        """Get a mapping from qubits to indices."""
        return {q: i for i, q in self.i2q.items()}

    @property
    def indices(self) -> Iterable[int]:
        """Get all the qubit indices managed by ``self``."""
        return self.i2q.keys()

    @property
    def qubits(self) -> Iterable[GridQubit]:
        """Get all the qubits manager by ``self``."""
        return self.i2q.values()

    def with_mapped_qubits(self, qubit_map: Callable[[GridQubit], GridQubit]) -> QubitMap:
        """Change the qubits involved in ``self`` without changing the associated indices.

        Args:
            qubit_map: a map from qubits to qubits that should associate a qubit
                to each of the qubits represented by ``self``.

        Raises:
            KeyError: if any qubit in ``self.qubits`` is not present in the keys of
                the provided ``qubit_map``.

        Returns:
            a new instance representing the updated mapping.

        """
        return QubitMap({i: qubit_map(q) for i, q in self.i2q.items()})

    def items(self) -> Iterable[tuple[int, GridQubit]]:
        """Get an iterator over each qubit and its corresponding index."""
        return self.i2q.items()

    def filter_by_qubits(self, qubits_to_keep: Iterable[GridQubit]) -> QubitMap:
        """Filter the qubit map to only keep qubits present in the provided ``qubits_to_keep``.

        Args:
            qubits_to_keep: the qubits to keep in the circuit.

        Returns:
            a copy of ``self`` for which the assertion
            ``set(return_value.qubits).issubset(qubits_to_keep)`` is ``True``.

        """
        return self.filter_by_qubit_indices(self.q2i[q] for q in qubits_to_keep if q in self.q2i)

    def filter_by_qubit_indices(self, qubit_indices_to_keep: Iterable[int]) -> QubitMap:
        """Filter the qubit map to only keep qubits present in ``qubit_indices_to_keep``.

        Args:
            qubit_indices_to_keep: the qubits to keep in the circuit.

        Returns:
            a copy of ``self`` with all the qubits associated to indices not in
            ``qubit_indices_to_keep`` removed.

        """
        kept_qubit_indices = frozenset(qubit_indices_to_keep)
        return QubitMap({i: q for i, q in self.i2q.items() if i in kept_qubit_indices})

    def to_circuit(self, shift_to_positive: bool = False) -> stim.Circuit:
        """Get a circuit with only ``QUBIT_COORDS`` instructions representing ``self``.

        Args:
            shift_to_positive: if ``True``, the qubit coordinates are shift such
                that they are all positive. Their relative positioning stays
                unchanged.

        Returns:
            a ``stim.Circuit`` containing only ``QUBIT_COORDS`` instructions.

        """
        shiftx, shifty = 0, 0
        if shift_to_positive:
            shiftx = -min((q.x for q in self.i2q.values()), default=0)
            shifty = -min((q.y for q in self.i2q.values()), default=0)
        ret = stim.Circuit()
        for qi, qubit in sorted(self.i2q.items(), key=lambda t: t[0]):
            ret.append(
                "QUBIT_COORDS",
                qi,
                StimCoordinates(qubit.x + shiftx, qubit.y + shifty).to_stim_coordinates(),
            )
        return ret

    def __getitem__(self, index: GridQubit) -> int:
        return self.q2i[index]

    def bounding_box(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Compute and return the bounding box of ``self``.

        Returns:
            ``(mins, maxes)`` where each of ``mins`` (resp. ``maxes``) is a pair
            of values ``(x, y)`` corresponding to the dimension.

        """
        coordinates = numpy.array([(q.x, q.y) for q in self.qubits])
        mins = numpy.min(coordinates, axis=0)
        maxes = numpy.max(coordinates, axis=0)
        return ((mins[0], mins[1]), (maxes[0], maxes[1]))

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the qubit map.

        The dictionary is intended to be used as a JSON object.

        """
        return {"i2q": [[qi, q.to_dict()] for qi, q in self.i2q.items()]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QubitMap:
        """Return a qubit map from its dictionary representation.

        Args:
            data: dictionary with the keys ``i2q`` and ``q2i``.

        Returns:
            a new instance of :class:`QubitMap` with the provided
            ``i2q`` and ``q2i``.

        """
        i2q = {int(qi): GridQubit.from_dict(q) for qi, q in data["i2q"]}
        return QubitMap(i2q)

    def qubit_bounds(self) -> tuple[GridQubit, GridQubit]:
        """Return the tightest possible bounding box containing all the qubits in ``self``.

        Raises:
            TQECError: if ``self`` is empty.

        Returns:
            ``(top_left, bottom_right)`` representing the bounding box of the qubits listed in
            ``self``.

        """
        if not self.i2q:
            raise TQECError("Cannot get the bounding box of an empty QubitMap.")
        qxs, qys = [q.x for q in self.i2q.values()], [q.y for q in self.i2q.values()]
        return GridQubit(min(qxs), min(qys)), GridQubit(max(qxs), max(qys))


def get_qubit_map(circuit: stim.Circuit) -> QubitMap:
    """Return the existing qubits and their coordinates at the end of the provided ``circuit``.

    Warning:
        This function, just like
        `stim.Circuit.get_final_qubit_coordinates <https://github.com/quantumlib/Stim/blob/main/doc/python_api_reference_vDev.md#stim.Circuit.get_final_qubit_coordinates>`_,
        returns the qubit coordinates **at the end** of the provided ``circuit``.

    Args:
        circuit: instance to get qubit coordinates from.

    Raises:
        TQECError: if any of the final qubits is not defined with exactly 2
            coordinates (we only consider qubits on a 2-dimensional grid).

    Returns:
        a mapping from qubit indices (keys) to qubit coordinates (values).

    """
    qubit_coordinates = circuit.get_final_qubit_coordinates()
    qubits: dict[int, GridQubit] = {}
    for qi, coords in qubit_coordinates.items():
        if len(coords) != 2:
            raise TQECError(
                "Qubits should be defined on exactly 2 spatial dimensions. "
                f"Found {qi} -> {coords} defined on {len(coords)} spatial dimensions."
            )
        x = round_or_fail(coords[0])
        y = round_or_fail(coords[1])
        qubits[qi] = GridQubit(x, y)
    return QubitMap(qubits)
