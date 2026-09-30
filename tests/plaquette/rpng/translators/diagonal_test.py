import pytest
import stim

from tqec.circuit.schedule import ScheduleError
from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator


def test_translator_supports_diagonal_schedule() -> None:
    translator = DefaultRPNGTranslator(DIAGONAL_SCHEDULE_FAMILY.measurement_schedule)
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


def test_translator_supports_partial_diagonal_description() -> None:
    translator = DefaultRPNGTranslator(DIAGONAL_SCHEDULE_FAMILY.measurement_schedule)
    desc = RPNGDescription.from_string("---- -x5- ---- -x7-")

    plaquette = translator.translate(desc)

    assert list(plaquette.circuit.schedule) == [0, 5, 7, 8]


def test_translator_rejects_interaction_after_measurement() -> None:
    translator = DefaultRPNGTranslator(measurement_schedule=6)
    desc = RPNGDescription.from_string("-x7- ---- ---- ----")

    with pytest.raises(ScheduleError):
        translator.translate(desc)
