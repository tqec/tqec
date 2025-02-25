"""Define the standard CSS-type surface code plaquettes."""

from __future__ import annotations

from typing import Literal

import stim


from tqec.circuit.moment import Moment, iter_stim_circuit_without_repeat_by_moments
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.utils.enums import Basis


def make_spatial_cube_arm_plaquette(
    basis: Basis,
    plaquette_kind: Literal["UP", "DOWN"],
    is_reverse: bool = False,
) -> Plaquette:
    """Make a plaquette for spatial cube arms.

    Args:
        basis: the basis of the plaquette.
        plaquette_kind: the kind of the plaquette.
        is_reverse: whether the plaquette has controlled-A reversed.

    Returns:
        A plaquette for spatial cube arms.
    """
    builder = _SpatialCubeArmPlaquetteBuilder(
        basis, plaquette_kind, is_reverse=is_reverse
    )
    return builder.build()


class _SpatialCubeArmPlaquetteBuilder:
    MERGEABLE_INSTRUCTIONS = frozenset(("M", "MZ", "MX", "R", "RZ", "RX"))
    BASE_NAME = "SPATIAL_CUBE_ARM"

    def __init__(
        self,
        basis: Basis,
        plaquette_kind: Literal["UP", "DOWN"],
        is_reverse: bool = False,
    ) -> None:
        self._basis = basis
        self._plaquette_kind = plaquette_kind
        self._is_reverse = is_reverse

        self._qubits = SquarePlaquetteQubits()
        match self._plaquette_kind:
            case "UP":
                self._moments = self._build_memory_moments_up()
            case "DOWN":
                self._moments = self._build_memory_moments_down()

        self._qubit_map = QubitMap(
            {0: self._qubits.syndrome_qubits[0]}
            | {i + 1: q for i, q in enumerate(self._qubits.data_qubits)}
        )

    def _get_plaquette_name(self) -> str:
        parts = [
            _SpatialCubeArmPlaquetteBuilder.BASE_NAME,
            self._basis.name,
            self._plaquette_kind,
        ]
        if self._is_reverse:
            parts.append("REVERSE")
        return "_".join(parts)

    def build(self) -> Plaquette:
        return Plaquette(
            self._get_plaquette_name(),
            self._qubits,
            ScheduledCircuit(self._moments, schedule=0, qubit_map=self._qubit_map),
            mergeable_instructions=self.MERGEABLE_INSTRUCTIONS,
        )

    def _build_memory_moments_up(self) -> list[Moment]:
        circuit = stim.Circuit()
        circuit.append("RX", [0], [])
        circuit.append("RZ", [3], [])
        circuit.append("TICK")
        circuit.append("CX", [0, 3], [])
        circuit.append("TICK")
        targ_order = [2, 1] if self._is_reverse else [1, 2]
        circuit.append(f"C{self._basis.name}", [0, targ_order[0]], [])
        circuit.append("TICK")
        circuit.append("TICK")
        circuit.append(f"C{self._basis.name}", [0, targ_order[1]], [])
        circuit.append("TICK")
        circuit.append("CX", [3, 0], [])
        return list(iter_stim_circuit_without_repeat_by_moments(circuit))

    def _build_memory_moments_down(self) -> list[Moment]:
        circuit = stim.Circuit()
        circuit.append("RZ", [1], [])
        circuit.append("TICK")
        circuit.append("RZ", [0], [])
        circuit.append("TICK")
        circuit.append("CX", [1, 0], [])
        circuit.append("TICK")
        targ_order = [4, 3] if self._is_reverse else [3, 4]
        circuit.append(f"C{self._basis.name}", [0, targ_order[0]], [])
        circuit.append("TICK")
        circuit.append("TICK")
        circuit.append(f"C{self._basis.name}", [0, targ_order[1]], [])
        circuit.append("TICK")
        circuit.append("CX", [0, 1], [])
        circuit.append("TICK")
        circuit.append("MX", [0], [])
        return list(iter_stim_circuit_without_repeat_by_moments(circuit))
