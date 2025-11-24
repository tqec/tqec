import stim

from tqec.compile.generation import generate_circuit
from tqec.plaquette._test_utils import make_surface_code_plaquette
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates._testing import FixedTemplate
from tqec.utils.enums import Basis
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def test_generate_circuit_one_plaquette() -> None:
    plaquette = make_surface_code_plaquette(Basis.X).project_on_boundary(PlaquetteOrientation.LEFT)
    circuit = generate_circuit(
        FixedTemplate([[0]]),
        2,
        Plaquettes(FrozenDefaultDict(default_value=plaquette)),
    )
    assert circuit.get_circuit() == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(1, 1) 2
RX 0
TICK
TICK
CX 0 1
TICK
TICK
TICK
CX 0 2
TICK
MX 0
""")


def test_generate_circuit_multiple_plaquettes() -> None:
    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {
                1: make_surface_code_plaquette(Basis.Z),
                2: make_surface_code_plaquette(Basis.X),
            }
        )
    )
    circuit = generate_circuit(FixedTemplate([[0, 1], [1, 0]]), k=1, plaquettes=plaquettes)
    assert circuit.get_circuit() == stim.Circuit("""
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(-1, 1) 1
QUBIT_COORDS(-1, 3) 2
QUBIT_COORDS(0, 0) 3
QUBIT_COORDS(0, 2) 4
QUBIT_COORDS(1, -1) 5
QUBIT_COORDS(1, 1) 6
QUBIT_COORDS(1, 3) 7
QUBIT_COORDS(2, 0) 8
QUBIT_COORDS(2, 2) 9
QUBIT_COORDS(3, -1) 10
QUBIT_COORDS(3, 1) 11
QUBIT_COORDS(3, 3) 12
RX 3 4 8 9
TICK
CZ 3 0 9 6
CX 4 1 8 5
TICK
CX 4 6 8 10
TICK
CZ 3 1 9 7
CX 4 2 8 6
TICK
CZ 3 5 9 11
TICK
CZ 3 6 9 12
CX 4 7 8 11
TICK
MX 3 4 8 9
""")
