from pprint import pprint

import stim

from tqec.plaquette.compilation.css import CSSPlaquetteCompiler
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.translators.default import DefaultRPNGTranslator


def test_zzzz() -> None:
    translator = DefaultRPNGTranslator()
    zzzz_standard = translator.translate(
        RPNGDescription.from_string("-z1- -z3- -z2- -z4-")
    )
    pprint(zzzz_standard.circuit.get_circuit())
    zzzz_css = CSSPlaquetteCompiler.compile(zzzz_standard)
    assert zzzz_css.circuit.get_circuit() == stim.Circuit("""\
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
R 4
TICK
H 0 1 2 3 4
TICK
CX 4 0
TICK
CX 4 2
TICK
CX 4 1
TICK
CX 4 3
TICK
TICK
H 0 1 2 3 4
TICK
M 4""")


def test_xxxx() -> None:
    translator = DefaultRPNGTranslator()
    xxxx_standard = translator.translate(
        RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    )
    pprint(xxxx_standard.circuit.get_circuit())
    xxxx_css = CSSPlaquetteCompiler.compile(xxxx_standard)
    assert xxxx_css.circuit.get_circuit() == stim.Circuit("""\
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
R 4
TICK
H 4
TICK
CX 4 0
TICK
CX 4 1
TICK
CX 4 2
TICK
CX 4 3
TICK
TICK
H 4
TICK
M 4""")


def test_zzzz_initialisation() -> None:
    translator = DefaultRPNGTranslator()
    zzzz_standard = translator.translate(
        RPNGDescription.from_string("zz1- zz3- zz2- zz4-")
    )
    pprint(zzzz_standard.circuit.get_circuit())
    zzzz_css = CSSPlaquetteCompiler.compile(zzzz_standard)
    assert zzzz_css.circuit.get_circuit() == stim.Circuit("""\
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
R 0 1 2 3 4
TICK
H 0 1 2 3 4
TICK
CX 4 0
TICK
CX 4 2
TICK
CX 4 1
TICK
CX 4 3
TICK
TICK
H 0 1 2 3 4
TICK
M 4""")


def test_zzzz_measurement() -> None:
    translator = DefaultRPNGTranslator()
    zzzz_standard = translator.translate(
        RPNGDescription.from_string("-z1z -z3z -z2z -z4z")
    )
    pprint(zzzz_standard.circuit.get_circuit())
    zzzz_css = CSSPlaquetteCompiler.compile(zzzz_standard)
    assert zzzz_css.circuit.get_circuit() == stim.Circuit("""\
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
R 4
TICK
H 0 1 2 3 4
TICK
CX 4 0
TICK
CX 4 2
TICK
CX 4 1
TICK
CX 4 3
TICK
TICK
H 0 1 2 3 4
TICK
M 0 1 2 3 4""")


def test_zzzz_x_initialisation() -> None:
    translator = DefaultRPNGTranslator()
    zzzz_standard = translator.translate(
        RPNGDescription.from_string("xz1- xz3- xz2- xz4-")
    )
    pprint(zzzz_standard.circuit.get_circuit())
    zzzz_css = CSSPlaquetteCompiler.compile(zzzz_standard)
    assert zzzz_css.circuit.get_circuit() == stim.Circuit("""\
QUBIT_COORDS(-1, -1) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(-1, 1) 2
QUBIT_COORDS(1, 1) 3
QUBIT_COORDS(0, 0) 4
R 0 1 2 3 4
TICK
H 4
TICK
CX 4 0
TICK
CX 4 2
TICK
CX 4 1
TICK
CX 4 3
TICK
TICK
H 0 1 2 3 4
TICK
M 4""")
