import stim

from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator


def test_default_translator_creation() -> None:
    DefaultRPNGTranslator()


def test_default_translator_from_ZZZZ_rpng_string() -> None:
    translator = DefaultRPNGTranslator()
    # Usual plaquette corresponding to the ZZZZ stabilizer.
    desc = RPNGDescription.from_string("-z1- -z3- -z2- -z4-")
    plaquette = translator.translate(desc)
    expected_circuit = stim.Circuit("""
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RX 4
TICK
CZ 4 0
TICK
CZ 4 2
TICK
CZ 4 1
TICK
CZ 4 3
TICK
TICK
MX 4
""")
    assert expected_circuit == plaquette.circuit.get_circuit()


def test_default_translator_from_ZXXZ_rpng_string() -> None:
    translator = DefaultRPNGTranslator()
    # Usual plaquette corresponding to the ZXXZ stabilizer with partial initialization.
    desc = RPNGDescription.from_string("-z1- zx2- zx4- -z5-")
    plaquette = translator.translate(desc)
    expected_circuit = stim.Circuit("""
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RX 4
RZ 1 2
TICK
CZ 4 0
TICK
CX 4 1
TICK
TICK
CX 4 2
TICK
CZ 4 3
TICK
MX 4
""")
    assert expected_circuit == plaquette.circuit.get_circuit()


def test_default_translator_from_arbitrary_rpng_string() -> None:
    translator = DefaultRPNGTranslator()
    # Arbitrary plaquette.
    desc = RPNGDescription.from_string("-x5h -z2z -x3x hz1-")
    plaquette = translator.translate(desc)
    expected_circuit = stim.Circuit("""
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
RX 4
H 3
TICK
CZ 4 3
TICK
CZ 4 1
TICK
CX 4 2
TICK
TICK
CX 4 0
TICK
MX 2 4
MZ 1
H 0
""")
    assert expected_circuit == plaquette.circuit.get_circuit()
