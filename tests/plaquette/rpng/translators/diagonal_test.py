import stim

from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.diagonal import DiagonalRPNGTranslator


def test_diagonal_translator_allows_schedule_6_gate() -> None:
    translator = DiagonalRPNGTranslator()
    desc = RPNGDescription.from_string("-z6- -z4- -z3- -z5-")
    plaquette = translator.translate(desc)
    expected_circuit = stim.Circuit("""
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RX 4
TICK
TICK
TICK
CZ 4 2
TICK
CZ 4 1
TICK
CZ 4 3
TICK
CZ 4 0
TICK
MX 4
""")
    assert expected_circuit == plaquette.circuit.get_circuit()
