"""Define the plaquettes for implementing arms for spatial cubes."""

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
    reset: Basis | None = None,
    measurement: Basis | None = None,
    is_reverse: bool = False,
    is_corner_trimmed: bool = False,
) -> Plaquette:
    """Make a plaquette for spatial cube arms.

    The below text represents the qubits in a stretched stabilizer ::

        a ----- b
        |       |
        |   c   |
        |       |
        d ------
        |       |
        |   e   |
        |       |
        f ----- g

    This is split into two plaquettes, with "UP" being (a, b, c, d) and "DOWN" being (d, e, f, g).

    Args:
        basis: the basis of the plaquette.
        plaquette_kind: the kind of the plaquette.
        reset: the logical basis for data qubit initialization. Defaults to ``None``
            which means "no initialization of data qubits".
        measurement: the logical basis for data qubit measurement. Defaults to
            ``None`` means "no measurement of data qubits".
        is_reverse: whether the schedules of controlled-A gates are reversed.
        is_corner_trimmed: whether the plaquette has corner trimmed, for "UP" plaquette
            the left top corner is trimmed, for "DOWN" plaquette the right bottom corner is trimmed.

    Returns:
        A plaquette for spatial cube arms.

    Notes:
        This method can generate 8 different plaquettes.
        UP-plaquettes:
        1. Qubits (a, b, c, d)
        2. Qubits (a, b, c, d) with controlled-A gates reversed
        DOWN-plaquettes:
        3. Qubits (d, e, f, g)
        4. Qubits (d, e, f, g) with controlled-A gates reversed
        Trimmed UP-plaquettes:
        5. Qubits (b, c, d)
        6. Qubits (b, c, d) with controlled-A gates reversed
        Trimmed DOWN-plaquettes:
        7. Qubits (d, e, f)
        8. Qubits (d, e, f) with controlled-A gates reversed

    """
    builder = _SpatialCubeArmPlaquetteBuilder(
        basis,
        plaquette_kind,
        is_reverse=is_reverse,
        is_corner_trimmed=is_corner_trimmed,
    )
    if reset is not None:
        builder.add_data_init_or_meas(reset, False)
    if measurement is not None:
        builder.add_data_init_or_meas(measurement, True)
    return builder.build()


class _SpatialCubeArmPlaquetteBuilder:
    MERGEABLE_INSTRUCTIONS = frozenset(("M", "MZ", "MX", "R", "RZ", "RX"))
    BASE_NAME = "SPATIAL_CUBE_ARM"

    def __init__(
        self,
        basis: Basis,
        plaquette_kind: Literal["UP", "DOWN"],
        is_reverse: bool = False,
        is_corner_trimmed: bool = False,
    ) -> None:
        self._basis = basis
        self._plaquette_kind: Literal["UP", "DOWN"] = plaquette_kind
        self._is_reverse = is_reverse
        self._is_corner_trimmed = is_corner_trimmed
        self._trimmed_qubit: int | None = None
        if self._is_corner_trimmed:
            self._trimmed_qubit = 1 if self._plaquette_kind == "UP" else 4

        self._qubits = SquarePlaquetteQubits()
        match self._plaquette_kind:
            case "UP":
                self._moments = self._build_memory_moments_up()
            case "DOWN":
                self._moments = self._build_memory_moments_down()

        self._qubit_map = QubitMap(
            {0: self._qubits.syndrome_qubits[0]} | {i + 1: q for i, q in enumerate(self._qubits.data_qubits)}
        )

        self._data_init: Basis | None = None
        self._data_meas: Basis | None = None

    def _get_data_qubits_for_init_or_meas(self) -> list[int]:
        match self._plaquette_kind:
            case "UP":
                return [2] if self._is_corner_trimmed else [1, 2]
            case "DOWN":
                return [3] if self._is_corner_trimmed else [3, 4]

    def _get_plaquette_name(self) -> str:
        parts = [
            _SpatialCubeArmPlaquetteBuilder.BASE_NAME,
            self._basis.name,
            self._plaquette_kind,
        ]
        if self._is_reverse:
            parts.append("REVERSE")
        if self._is_corner_trimmed:
            parts.append("CORNER_TRIMMED")
        if self._data_init is not None:
            parts.append(f"datainit({self._data_init.name})")
        if self._data_meas is not None:
            parts.append(f"datameas({self._data_meas.name})")
        return "_".join(parts)

    def build(self) -> Plaquette:
        return Plaquette(
            self._get_plaquette_name(),
            self._qubits,
            ScheduledCircuit(self._moments, schedule=0, qubit_map=self._qubit_map),
            mergeable_instructions=self.MERGEABLE_INSTRUCTIONS,
        )

    def _append_ctrl_op_to_data_qubit(self, circuit: stim.Circuit, target: int) -> None:
        if self._trimmed_qubit is not None and target == self._trimmed_qubit:
            circuit.append("TICK")
        else:
            circuit.append(f"C{self._basis.name}", [0, target], [])

    def _build_memory_moments_up(self) -> list[Moment]:
        """Implement circuit for the following plaquette::

        1 ----- 2
        |       |
        |   0   |
        |       |
        3 -----
        """
        circuit = stim.Circuit()
        circuit.append("RX", [0], [])
        circuit.append("RZ", [3], [])
        circuit.append("TICK")
        circuit.append("CX", [0, 3], [])
        circuit.append("TICK")
        targ_order = [2, 1] if self._is_reverse else [1, 2]
        self._append_ctrl_op_to_data_qubit(circuit, targ_order[0])
        circuit.append("TICK")
        circuit.append("TICK")
        self._append_ctrl_op_to_data_qubit(circuit, targ_order[1])
        circuit.append("TICK")
        circuit.append("CX", [3, 0], [])
        return list(iter_stim_circuit_without_repeat_by_moments(circuit))

    def _build_memory_moments_down(self) -> list[Moment]:
        """Implement circuit for the following plaquette::

        1 -----
        |       |
        |   0   |
        |       |
        3 ----- 4
        """
        circuit = stim.Circuit()
        circuit.append("RZ", [1], [])
        circuit.append("TICK")
        circuit.append("RZ", [0], [])
        circuit.append("TICK")
        circuit.append("CX", [1, 0], [])
        circuit.append("TICK")
        targ_order = [4, 3] if self._is_reverse else [3, 4]
        self._append_ctrl_op_to_data_qubit(circuit, targ_order[0])
        circuit.append("TICK")
        circuit.append("TICK")
        self._append_ctrl_op_to_data_qubit(circuit, targ_order[1])
        circuit.append("TICK")
        circuit.append("CX", [0, 1], [])
        circuit.append("TICK")
        circuit.append("MX", [0], [])
        return list(iter_stim_circuit_without_repeat_by_moments(circuit))

    def add_data_init_or_meas(self, basis: Basis, is_measurement: bool) -> None:
        if is_measurement:
            moment_index = -1
            self._data_meas = basis
        else:
            moment_index = 0
            self._data_init = basis
        op = "M" if is_measurement else "R"
        self._moments[moment_index].append(f"{op}{basis.value}", self._get_data_qubits_for_init_or_meas(), [])
