import pytest

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.tree.annotators.detectors import LookbackStack
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import Template
from tqec.templates.qubit import QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict

_TRANSLATOR = DefaultRPNGTranslator()
_EMPTY_PLAQUETTE = _TRANSLATOR.translate(RPNGDescription.empty())


@pytest.fixture(name="template")
def template_fixture() -> Template:
    return QubitTemplate()


@pytest.fixture(name="plaquettes")
def plaquettes_fixture() -> Plaquettes:
    return Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))


@pytest.fixture(name="measurement_records")
def measurement_records_fixture() -> MeasurementRecordsMap:
    return MeasurementRecordsMap()


def test_stack_creation() -> None:
    LookbackStack()


def test_stack_append(
    template: Template,
    plaquettes: Plaquettes,
    measurement_records: MeasurementRecordsMap,
) -> None:
    stack = LookbackStack()
    stack.append(template, plaquettes, measurement_records)
    assert len(stack) == 1


def test_stack_len(
    template: Template,
    plaquettes: Plaquettes,
    measurement_records: MeasurementRecordsMap,
) -> None:
    stack = LookbackStack()
    for i in range(12):
        assert len(stack) == i
        stack.append(template, plaquettes, measurement_records)
        assert len(stack) == i + 1
    stack.enter_repeat_block()
    with pytest.raises(
        TQECException,
        match="^Cannot get a meaningful stack length when a REPEAT block is in construction.$",
    ):
        len(stack)
    stack.enter_repeat_block()
    with pytest.raises(
        TQECException,
        match="^Cannot get a meaningful stack length when a REPEAT block is in construction.$",
    ):
        len(stack)
    stack.close_repeat_block(1)
    with pytest.raises(
        TQECException,
        match="^Cannot get a meaningful stack length when a REPEAT block is in construction.$",
    ):
        len(stack)
    stack.close_repeat_block(1)
    assert len(stack) == 12


def test_stack_repeat_block_append(
    template: Template,
    plaquettes: Plaquettes,
    measurement_records: MeasurementRecordsMap,
) -> None:
    stack = LookbackStack()
    stack.append(template, plaquettes, measurement_records)
    stack.enter_repeat_block()
    stack.append(template, plaquettes, measurement_records)
    stack.append(template, plaquettes, measurement_records)
    stack.close_repeat_block(2)
    assert len(stack) == 5
    stack.enter_repeat_block()
    stack.close_repeat_block(4)
    assert len(stack) == 5
    stack.enter_repeat_block()
    stack.enter_repeat_block()
    stack.append(template, plaquettes, measurement_records)
    stack.close_repeat_block(3)
    stack.close_repeat_block(3)
    assert len(stack) == 14


def test_stack_erroneous_repeat_block() -> None:
    stack = LookbackStack()
    with pytest.raises(TQECException, match="Only got 1 < 2 entries in the stack..*"):
        stack.close_repeat_block(4)


def test_stack_lookback(
    template: Template,
    plaquettes: Plaquettes,
    measurement_records: MeasurementRecordsMap,
) -> None:
    stack = LookbackStack()
    with pytest.raises(TQECException, match="Cannot look back a negative number of rounds..*"):
        stack.lookback(-1)
    # Valid query on empty stack.
    ts, ps, _ = stack.lookback(0)
    assert len(ts) == 0
    assert len(ps) == 0
    ts, ps, _ = stack.lookback(3)
    assert len(ts) == 0
    assert len(ps) == 0

    stack.append(template, plaquettes, measurement_records)
    # Valid query on a non-empty stack.
    ts, ps, _ = stack.lookback(0)
    assert len(ts) == 0
    assert len(ps) == 0
    ts, ps, _ = stack.lookback(3)
    assert len(ts) == 1
    assert len(ps) == 1

    stack.enter_repeat_block()
    # Valid query on a non-empty stack, without any entries in the current repeat block.
    ts, ps, _ = stack.lookback(3)
    assert len(ts) == 1
    assert len(ps) == 1

    stack.append(template, plaquettes, measurement_records)
    stack.append(template, plaquettes, measurement_records)
    # Valid query on a non-empty stack, with entries in the current repeat block.
    ts, ps, _ = stack.lookback(2)
    assert len(ts) == 2
    assert len(ps) == 2
    ts, ps, _ = stack.lookback(5)
    assert len(ts) == 3
    assert len(ps) == 3

    stack.close_repeat_block(2)
    assert len(stack) == 5  # To remember the size of the stack
    # Valid query on a non-empty stack, with entries in a previous repeat block.
    ts, ps, _ = stack.lookback(2)
    assert len(ts) == 2
    assert len(ps) == 2
    ts, ps, _ = stack.lookback(5)
    assert len(ts) == 5
    assert len(ps) == 5
    ts, ps, _ = stack.lookback(7)
    assert len(ts) == 5
    assert len(ps) == 5
