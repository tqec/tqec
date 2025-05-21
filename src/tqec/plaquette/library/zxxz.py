"""Define the ZXXZ-type surface code plaquettes."""

from __future__ import annotations

from typing import Literal

import stim

from tqec.circuit.moment import Moment, iter_stim_circuit_without_repeat_by_moments
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import ScheduledCircuit
from tqec.plaquette.enums import PlaquetteSide
from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.utils.enums import Basis


def make_zxxz_surface_code_plaquette(
    basis: Literal["X", "Z"],
    data_initialization: Basis | None = None,
    data_measurement: Basis | None = None,
    x_boundary_orientation: Literal["HORIZONTAL", "VERTICAL"] = "VERTICAL",
    init_meas_only_on_side: PlaquetteSide | None = None,
) -> Plaquette:
    """Create a ZXXZ-type surface code plaquette. The circuit is adapted to
    superconducting qubits architecture s.t. all CNOTs are compiled to the CZ
    gates and additional Hadamard gates. Only Z basis reset and measurement are
    supported.

    Args:
        basis: the basis of the plaquette.
        data_initialization: the logical basis for data initialization.
        data_measurement: the logical basis for data measurement.
        x_boundary_orientation: the orientation of the X boundary.
        init_meas_only_on_side: the side for data initialization and measurement.

    """
    builder = _ZXXZPlaquetteBuilder(basis, x_boundary_orientation)
    if data_initialization is not None:
        builder.add_data_init_or_meas(data_initialization, False, init_meas_only_on_side)
    if data_measurement is not None:
        builder.add_data_init_or_meas(data_measurement, True, init_meas_only_on_side)
    return builder.build()


class _ZXXZPlaquetteBuilder:
    MERGEABLE_INSTRUCTIONS = frozenset(("H", "R", "RZ", "M", "MZ"))
    BASE_NAME = "ZXXZ"

    def __init__(
        self,
        basis: Literal["X", "Z"],
        x_boundary_orientation: Literal["HORIZONTAL", "VERTICAL"] = "HORIZONTAL",
    ) -> None:
        self._basis: Literal["X", "Z"] = basis
        self._x_boundary_orientation = x_boundary_orientation
        self._moments: list[Moment] = self._build_memory_moments()
        self._qubits = SquarePlaquetteQubits()
        self._qubit_map = QubitMap(
            {0: self._qubits.syndrome_qubits[0]} | {i + 1: q for i, q in enumerate(self._qubits.data_qubits)}
        )
        self._data_init: tuple[Basis, PlaquetteSide | None] | None = None
        self._data_meas: tuple[Basis, PlaquetteSide | None] | None = None

    def _get_plaquette_name(self) -> str:
        parts = [
            _ZXXZPlaquetteBuilder.BASE_NAME,
            f"basis({self._basis})",
            self._x_boundary_orientation,
        ]
        if self._data_init is not None:
            side_part = f",{self._data_init[1].name}" if self._data_init[1] is not None else ""
            parts.append(f"datainit({self._data_init[0].name}{side_part})")
        if self._data_meas is not None:
            side_part = f",{self._data_meas[1].name}" if self._data_meas[1] is not None else ""
            parts.append(f"datameas({self._data_meas[0].name}{side_part})")
        return "_".join(parts)

    def build(self) -> Plaquette:
        return Plaquette(
            self._get_plaquette_name(),
            self._qubits,
            ScheduledCircuit(
                self._moments,
                schedule=0,
                qubit_map=self._qubit_map,
            ),
            mergeable_instructions=self.MERGEABLE_INSTRUCTIONS,
        )

    def add_data_init_or_meas(
        self,
        basis: Basis,
        is_measurement: bool,
        only_on_side: PlaquetteSide | None = None,
    ) -> None:
        dqs_considered = self._get_data_qubits(only_on_side)
        if not is_measurement:
            self._moments[0].append("R", dqs_considered, [])
            h_moment_idx = 1
            self._data_init = basis, only_on_side
        else:
            self._moments[-1].append("M", dqs_considered, [])
            h_moment_idx = -2
            self._data_meas = basis, only_on_side

        basis_change_dqs = self._get_init_meas_basis_change_dqs(basis.value, dqs_considered)
        # It's important to ignore the H gates on the data qubits that are not
        # considered for initialization/measurement to avoid adding unneeded H.
        h_cancel_out = self._moments[h_moment_idx].qubits_indices.intersection(dqs_considered)
        h_targets = {0} | basis_change_dqs ^ h_cancel_out
        self._moments[h_moment_idx] = Moment(stim.Circuit(f"H {' '.join(map(str, h_targets))}"))

    def _build_memory_moments(self) -> list[Moment]:
        basis_changes: list[int] = [0]
        # when x boundary is horizontal, a moment of transversal H is applied
        # to data qubits after/before the initialization/measurement to map
        # the xzzx stabilizer to zxxz stabilizer and back
        if self._x_boundary_orientation == "HORIZONTAL":
            basis_changes.extend(range(1, 5))
        H_FOR_BASIS_CHANGE = "H " + " ".join(map(str, basis_changes))
        # adjust cz order to make the hook errors perpendicular to the boundary
        match self._basis, self._x_boundary_orientation:
            case ("X", "HORIZONTAL") | ("Z", "VERTICAL"):
                cz_order = [1, 2, 3, 4]
            case _:
                cz_order = [1, 3, 2, 4]

        H_ON_ALL_DQS = "H " + " ".join(map(str, range(1, 5)))
        circuit = stim.Circuit(f"""
R 0
TICK
{H_FOR_BASIS_CHANGE}
TICK
CZ 0 {cz_order[0]}
TICK
{H_ON_ALL_DQS}
TICK
CZ 0 {cz_order[1]}
TICK
CZ 0 {cz_order[2]}
TICK
{H_ON_ALL_DQS}
TICK
CZ 0 {cz_order[3]}
TICK
{H_FOR_BASIS_CHANGE}
TICK
M 0
""")
        return list(iter_stim_circuit_without_repeat_by_moments(circuit))

    def _get_data_qubits(self, only_on_side: PlaquetteSide | None = None) -> list[int]:
        if only_on_side is None:
            return [1, 2, 3, 4]
        target_qubits = self._qubits.get_qubits_on_side(only_on_side)
        return sorted(self._qubit_map.q2i[q] for q in target_qubits)

    def _get_init_meas_basis_change_dqs(
        self, init_or_meas_basis: Literal["X", "Z"], dqs_considered: list[int]
    ) -> set[int]:
        x_is_vertical = self._x_boundary_orientation == "VERTICAL"
        is_same_basis = self._basis == init_or_meas_basis
        x_basis_dqs = {1, 4} if x_is_vertical ^ is_same_basis else {2, 3}
        return x_basis_dqs.intersection(dqs_considered)
