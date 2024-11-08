"""Defines core data-structures to handle the mapping between qubit coordinates
(as :class:`~tqec.circuit.qubit.GridQubit` instances) and qubit indices.

A bijection from qubit coordinates to qubit indices is represented by
:class:`QubitMap` defined in this module.

This bijection can be obtained from a ``stim.Circuit`` instance by using
:func:`get_qubit_map`.
"""

from __future__ import annotations

import functools
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable

import stim

from tqec.circuit.qubit import GridQubit
from tqec.exceptions import TQECException
from tqec.scale import round_or_fail


@dataclass(frozen=True)
class QubitMap:
    """Represent a bijection between :class:`~tqec.circuit.qubit.GridQubit`
    instances and indices.

    This class aims at representing a bidirectional mapping (hence the
    "bijection") between qubits and their associated indices.

    Raises:
        TQECException: if the provided mapping from indices to qubits is not a
            bijection (i.e., if at least to values represent the same qubit).
    """

    i2q: dict[int, GridQubit] = field(default_factory=dict)

    def __post_init__(self) -> None:
        qubit_counter = Counter(self.i2q.values())
        if len(qubit_counter) != len(self.i2q):
            duplicated_qubits = frozenset(
                q for q in qubit_counter if qubit_counter[q] > 1
            )
            raise TQECException(
                f"Found qubit(s) with more than one index: {duplicated_qubits}."
            )

    @staticmethod
    def from_qubits(qubits: Iterable[GridQubit]) -> QubitMap:
        """Creates a qubit map from the provided ``qubits``, associating
        indices using the order in which qubits are provided."""
        return QubitMap(dict(enumerate(qubits)))

    @staticmethod
    def from_circuit(circuit: stim.Circuit) -> QubitMap:
        return get_qubit_map(circuit)

    @functools.cached_property
    def q2i(self) -> dict[GridQubit, int]:
        return {q: i for i, q in self.i2q.items()}

    @property
    def indices(self) -> Iterable[int]:
        return self.i2q.keys()

    @property
    def qubits(self) -> Iterable[GridQubit]:
        return self.i2q.values()

    def with_mapped_qubits(
        self, qubit_map: Callable[[GridQubit], GridQubit]
    ) -> QubitMap:
        """Change the qubits involved in ``self`` without changing the
        associated indices.

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
        return self.i2q.items()

    def filter_by_qubits(self, qubits_to_keep: Iterable[GridQubit]) -> QubitMap:
        """Filter the qubit map to only keep qubits present in the provided
        ``qubits_to_keep``.

        Args:
            qubits_to_keep: the qubits to keep in the circuit.

        Returns:
            a copy of ``self`` for which the assertion
            ``set(return_value.qubits).issubset(qubits_to_keep)`` is ``True``.
        """
        kept_qubits = frozenset(qubits_to_keep)
        return QubitMap({i: q for i, q in self.i2q.items() if q in kept_qubits})

    def to_circuit(self) -> stim.Circuit:
        """Get a circuit with only ``QUBIT_COORDS`` instructions representing
        ``self``."""
        ret = stim.Circuit()
        for qi, qubit in sorted(self.i2q.items(), key=lambda t: t[0]):
            ret.append("QUBIT_COORDS", qi, (float(qubit.x), float(qubit.y)))
        return ret


def get_qubit_map(circuit: stim.Circuit) -> QubitMap:
    """Returns the existing qubits and their coordinates at the end of the
    provided ``circuit``.

    Warning:
        This function, just like
        `stim.Circuit.get_final_qubit_coordinates <https://github.com/quantumlib/Stim/blob/main/doc/python_api_reference_vDev.md#stim.Circuit.get_final_qubit_coordinates>`_,
        returns the qubit coordinates **at the end** of the provided ``circuit``.

    Args:
        circuit: instance to get qubit coordinates from.

    Raises:
        TQECException: if any of the final qubits is not defined with exactly 2
            coordinates (we only consider qubits on a 2-dimensional grid).

    Returns:
        a mapping from qubit indices (keys) to qubit coordinates (values).
    """
    qubit_coordinates = circuit.get_final_qubit_coordinates()
    qubits: dict[int, GridQubit] = {}
    for qi, coords in qubit_coordinates.items():
        if len(coords) != 2:
            raise TQECException(
                "Qubits should be defined on exactly 2 spatial dimensions. "
                f"Found {qi} -> {coords} defined on {len(coords)} spatial dimensions."
            )
        x = round_or_fail(coords[0])
        y = round_or_fail(coords[1])
        qubits[qi] = GridQubit(x, y)
    return QubitMap(qubits)
