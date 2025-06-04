import pytest
import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule import Schedule, ScheduledCircuit, ScheduleException
from tqec.utils.exceptions import TQECException

_VALID_SCHEDULED_CIRCUITS = [
    stim.Circuit(""),
    stim.Circuit("H 0 1 2"),
    stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"),
    stim.Circuit("H 0 1 2\nTICK\nTICK\nTICK\nH 0 1 2"),
    stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1"),
    stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nH 0\nTICK\nM 0"),
    stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0\nTICK\nCX 0 1\nTICK\nM 0 1"),
]


def test_scheduled_circuit_construction() -> None:
    ScheduledCircuit.empty()
    ScheduledCircuit.from_circuit(stim.Circuit(""))
    ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"))
    ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), 1)
    ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), 498567)
    ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), [0, 1])
    ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), Schedule.from_offsets([0, 3]))

    with pytest.raises(ScheduleException):
        ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), -1)
    with pytest.raises(ScheduleException):
        ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), [1])
    with pytest.raises(ScheduleException):
        ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), [1, 2, 3])
    with pytest.raises(ScheduleException):
        ScheduledCircuit.from_circuit(stim.Circuit("REPEAT 10{\nH 0 1 2\n}"), [1])

    ScheduledCircuit([], 0, QubitMap())
    moments = [Moment(stim.Circuit("H 0 1 2")), Moment(stim.Circuit("H 0 1 2"))]
    i2q = QubitMap({i: GridQubit(i, i) for i in range(3)})
    ScheduledCircuit(moments, 0, i2q)
    ScheduledCircuit(moments, [0, 1], i2q)
    ScheduledCircuit(moments, Schedule.from_offsets([0, 1]), i2q)
    with pytest.raises(ScheduleException):
        ScheduledCircuit(moments, -1, i2q)
    with pytest.raises(ScheduleException):
        ScheduledCircuit(moments, [0], i2q)
    with pytest.raises(ScheduleException):
        ScheduledCircuit(moments, [0, 1, 2], i2q)

    with pytest.raises(ScheduleException):
        ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nQUBIT_COORDS(0, 0) 0\nH 0 1 2"))
    moments = [
        Moment(stim.Circuit("H 0 1 2")),
        Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0 1 2")),
    ]
    with pytest.raises(ScheduleException):
        ScheduledCircuit(moments, 0, i2q)


def test_scheduled_circuit_schedule_property() -> None:
    assert ScheduledCircuit.empty().schedule.schedule == []
    assert ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2")).schedule.schedule == [0, 1]
    assert ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), [4, 56]).schedule.schedule == [4, 56]
    moments = [Moment(stim.Circuit("H 0 1 2")), Moment(stim.Circuit("H 0 1 2"))]
    i2q = QubitMap({i: GridQubit(i, i) for i in range(3)})
    assert ScheduledCircuit(moments, 0, i2q).schedule.schedule == [0, 1]


@pytest.mark.parametrize("circuit", _VALID_SCHEDULED_CIRCUITS)
def test_scheduled_circuit_get_circuit(circuit: stim.Circuit) -> None:
    assert ScheduledCircuit.from_circuit(circuit).get_circuit() == circuit


def test_scheduled_circuit_get_qubit_coords_definition_preamble() -> None:
    assert ScheduledCircuit.from_circuit(stim.Circuit("H 0 1")).get_qubit_coords_definition_preamble() == stim.Circuit(
        ""
    )
    assert ScheduledCircuit.from_circuit(
        stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0 1")
    ).get_qubit_coords_definition_preamble() == stim.Circuit("QUBIT_COORDS(0, 0) 0")
    assert ScheduledCircuit.from_circuit(
        stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(-2345, 3456) 1\nH 0 1")
    ).get_qubit_coords_definition_preamble() == stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(-2345, 3456) 1")


@pytest.mark.parametrize("circuit", _VALID_SCHEDULED_CIRCUITS)
def test_scheduled_circuit_get_repeated_circuit(circuit: stim.Circuit) -> None:
    for repetitions in [2, 6, 1345]:
        scheduled_circuit = ScheduledCircuit.from_circuit(circuit)
        coords_preamble = scheduled_circuit.get_qubit_coords_definition_preamble()
        body_without_coords = scheduled_circuit.get_circuit(include_qubit_coords=False)
        expected_circuit = stim.Circuit(f"REPEAT {repetitions} {{\n{body_without_coords}\nTICK\n}}")
        assert (
            ScheduledCircuit.from_circuit(circuit).get_repeated_circuit(repetitions, include_qubit_coords=False)
            == expected_circuit
        )
        assert ScheduledCircuit.from_circuit(circuit).get_repeated_circuit(repetitions) == (
            coords_preamble + expected_circuit
        )


def test_scheduled_circuit_get_circuit_with_schedule() -> None:
    circuit = ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 0 1 2"), [0, 3])
    assert circuit.get_circuit() == stim.Circuit("H 0 1 2\nTICK\nTICK\nTICK\nH 0 1 2")


def test_scheduled_circuit_get_circuit_without_coords() -> None:
    circuit = ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1"))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("H 0 1")


def test_scheduled_circuit_qubits() -> None:
    assert ScheduledCircuit.from_circuit(stim.Circuit("")).qubits == frozenset()
    assert ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2")).qubits == frozenset()
    assert ScheduledCircuit.from_circuit(
        stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1")
    ).qubits == frozenset([GridQubit(0, 0), GridQubit(0, 1)])
    assert ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nH 0\nTICK\nM 0")).qubits == frozenset(
        [GridQubit(0, 0)]
    )


def test_scheduled_circuit_map_qubit_indices() -> None:
    circuit = ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1"))
    mapped_circuit = circuit.map_qubit_indices({0: 13, 1: 75})
    assert mapped_circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0.0, 0.0) 13\nQUBIT_COORDS(0.0, 1.0) 75\nH 13 75")
    assert circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1")
    circuit.map_qubit_indices({0: 13, 1: 75}, inplace=True)
    assert circuit.get_circuit() == mapped_circuit.get_circuit()

    circuit = ScheduledCircuit.from_circuit(
        stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nX 0\nTICK\nM 0\nDETECTOR(0, 0) rec[-1]")
    )
    circuit.map_qubit_indices({0: 13, 1: 75}, inplace=True)
    assert circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0.0, 0.0) 13\nX 13\nTICK\nM 13\nDETECTOR(0, 0) rec[-1]")


def test_scheduled_circuit_map_to_qubits() -> None:
    qubit_map = {GridQubit(0, 0): GridQubit(18, 345), GridQubit(0, 1): GridQubit(1, 0)}
    circuit = ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1"))
    mapped_circuit = circuit.map_to_qubits(lambda q: qubit_map[q])
    assert mapped_circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(18, 345) 0\nQUBIT_COORDS(1, 0) 1\nH 0 1")
    assert circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0.0, 0.0) 0\nQUBIT_COORDS(0.0, 1.0) 1\nH 0 1")
    circuit.map_to_qubits(lambda q: qubit_map[q], inplace_qubit_map=True)
    assert circuit.get_circuit() == mapped_circuit.get_circuit()


def test_scheduled_circuit_moment_at_schedule() -> None:
    circuit = ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2\nTICK\nH 2 1 0"))
    assert circuit.moment_at_schedule(0).circuit == stim.Circuit("H 0 1 2")
    assert circuit.moment_at_schedule(1).circuit == stim.Circuit("H 2 1 0")
    assert circuit.moment_at_schedule(-1).circuit == stim.Circuit("H 2 1 0")
    assert circuit.moment_at_schedule(-2).circuit == stim.Circuit("H 0 1 2")
    with pytest.raises(TQECException):
        circuit.moment_at_schedule(2)
    with pytest.raises(TQECException):
        circuit.moment_at_schedule(-3)


def test_scheduled_circuit_modification() -> None:
    circuit = ScheduledCircuit.empty()
    circuit.append_new_moment(Moment(stim.Circuit("H 0 1 2")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("H 0 1 2")
    circuit.add_to_schedule_index(0, Moment(stim.Circuit("H 3")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("H 0 1 2 3")
    circuit.add_to_schedule_index(4, Moment(stim.Circuit("CX 0 1 2 3")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit(
        "H 0 1 2 3\nTICK\nTICK\nTICK\nTICK\nCX 0 1 2 3"
    )
    circuit.add_to_schedule_index(2, Moment(stim.Circuit("CX 0 1 2 3")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit(
        "H 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3"
    )
    circuit.append_new_moment(Moment(stim.Circuit("H 2 1 0")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit(
        "H 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3\nTICK\nH 2 1 0"
    )
    circuit.add_to_schedule_index(-1, Moment(stim.Circuit("H 3")))
    assert circuit.get_circuit(include_qubit_coords=False) == stim.Circuit(
        "H 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3\nTICK\nTICK\nCX 0 1 2 3\nTICK\nH 2 1 0 3"
    )


def test_scheduled_circuit_append_annotation() -> None:
    circuit = ScheduledCircuit.empty()
    circuit.append_new_moment(Moment(stim.Circuit("H 0 1 2")))
    circuit.append_annotation(stim.CircuitInstruction("DETECTOR", [stim.target_rec(-1)], [0, 0]))
    circuit.append_observable(0, [stim.target_rec(-1)])
    with pytest.raises(
        TQECException,
        match="^The provided instruction is not an annotation, which is disallowed by the append_annotation method.$",
    ):
        circuit.append_annotation(stim.CircuitInstruction("H", [0, 1], []))


def test_scheduled_circuit_filter_by_qubit() -> None:
    circuit = ScheduledCircuit(
        [Moment(stim.Circuit("H 0 1 2"))],
        schedule=0,
        qubit_map=QubitMap({i: GridQubit(i, i) for i in range(3)}),
    )
    filtered_circuit = circuit.filter_by_qubits([GridQubit(i, i) for i in range(3)])
    assert filtered_circuit.get_circuit() == circuit.get_circuit()
    assert filtered_circuit.schedule == circuit.schedule

    filtered_circuit = circuit.filter_by_qubits([GridQubit(0, 0), GridQubit(0, 1)])
    assert filtered_circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
    assert filtered_circuit.schedule == circuit.schedule

    circuit.append_new_moment(Moment(stim.Circuit("H 1 2")))
    filtered_circuit = circuit.filter_by_qubits([GridQubit(0, 0), GridQubit(0, 1)])
    assert filtered_circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
    assert filtered_circuit.schedule == Schedule([0])
