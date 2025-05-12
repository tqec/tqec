import numpy
import pytest
import stim

from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.compile.specs.library.generators.extended_stabilizers import (
    make_spatial_cube_arm_plaquettes,
)
from tqec.plaquette.plaquette import Plaquettes
from tqec.utils.enums import Basis
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import Shift2D


@pytest.mark.parametrize(
    "basis,is_reverse",
    [(Basis.X, False), (Basis.Z, False), (Basis.X, True), (Basis.Z, True)],
)
def test_spatial_cube_arm_plaquette(basis: Basis, is_reverse: bool) -> None:
    up, down = make_spatial_cube_arm_plaquettes(basis, is_reverse=is_reverse)
    scheduled_circuit = generate_circuit_from_instantiation(
        numpy.array([[1], [2]]),
        Plaquettes(FrozenDefaultDict({1: up, 2: down})),
        increments=Shift2D(2, 2),
    )
    circuit = scheduled_circuit.get_circuit()
    b = basis.value.upper()
    lf, rf = ("", "_") if is_reverse else ("_", "")
    assert circuit.has_flow(stim.Flow(f"1 -> {b}{lf}{b}__{b}{rf}{b} xor rec[0]"))
    assert circuit.has_flow(stim.Flow(f"{b}{lf}{b}__{b}{rf}{b} -> rec[0]"))
