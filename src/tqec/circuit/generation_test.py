import stim

from tqec.circuit.generation import generate_circuit
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.library import make_css_surface_code_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.indices._testing import FixedTemplate


def test_generate_circuit_one_plaquette() -> None:
    plaquette = make_css_surface_code_plaquette("Z").project_on_boundary(
        PlaquetteOrientation.LEFT
    )
    circuit = generate_circuit(
        FixedTemplate([[0]]),
        2,
        Plaquettes(FrozenDefaultDict(default_factory=lambda: plaquette)),
    )
    assert circuit.get_circuit() == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(1, 1) 2
R 0
TICK
TICK
CX 1 0
TICK
TICK
CX 2 0
TICK
M 0
""")


def test_generate_circuit_multiple_plaquettes() -> None:
    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {
                1: make_css_surface_code_plaquette("Z"),
                2: make_css_surface_code_plaquette("X"),
            }
        )
    )
    circuit = generate_circuit(
        FixedTemplate([[0, 1], [1, 0]]), k=1, plaquettes=plaquettes
    )
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
R 3 9
RX 4 8
TICK
CX 0 3 8 5 4 1 6 9
TICK
CX 5 3 8 6 4 2 11 9
TICK
CX 1 3 8 10 4 6 7 9
TICK
CX 6 3 8 11 4 7 12 9
TICK
M 3 9
MX 4 8
""")
