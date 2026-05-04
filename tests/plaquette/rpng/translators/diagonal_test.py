import stim

from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator


def test_diagonal_translator_allows_schedule_6_gate() -> None:
    translator = DefaultRPNGTranslator(schedule_family=DIAGONAL_SCHEDULE_FAMILY)
    desc = RPNGDescription.from_string("-x7- -x5- -x4- -x6-")
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
TICK
CX 4 2
TICK
CX 4 1
TICK
CX 4 3
TICK
CX 4 0
TICK
MX 4
""")
    assert expected_circuit == plaquette.circuit.get_circuit()
