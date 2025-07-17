import numpy
import pytest
import stim

from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.compile.specs.library.generators.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.compile.specs.library.generators.extended_stabilizers import get_extended_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.enums import Basis
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import Shift2D


@pytest.mark.parametrize(
    "basis,is_reversed",
    [(Basis.X, False), (Basis.Z, False), (Basis.X, True), (Basis.Z, True)],
)
def test_extended_plaquette(basis: Basis, is_reversed: bool) -> None:
    up, down = get_extended_plaquette(
        RPNGDescription.from_basis_and_schedule(basis, EXTENDED_PLAQUETTE_SCHEDULES[is_reversed]),
        is_reversed=is_reversed,
    )
    scheduled_circuit = generate_circuit_from_instantiation(
        numpy.array([[1], [2]]),
        Plaquettes(FrozenDefaultDict({1: up, 2: down})),
        increments=Shift2D(2, 2),
    )
    circuit = scheduled_circuit.get_circuit()
    b = basis.value.upper() if basis is not None else "_"
    lf, rf = ("", "_") if is_reversed else ("_", "")
    assert circuit.has_flow(stim.Flow(f"1 -> {b}{lf}{b}__{b}{rf}{b} xor rec[0]"))
    assert circuit.has_flow(stim.Flow(f"{b}{lf}{b}__{b}{rf}{b} -> rec[0]"))
