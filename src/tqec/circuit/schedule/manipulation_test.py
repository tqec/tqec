import pytest
import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.circuit.schedule.manipulation import (
    merge_scheduled_circuits,
    relabel_circuits_qubit_indices,
    remove_duplicate_instructions,
)
from tqec.exceptions import TQECWarning


def test_remove_duplicate_instructions() -> None:
    instructions: list[stim.CircuitInstruction] = list(
        iter(stim.Circuit("H 0 0 0 2 0 0 0 0 1 1 2 2 0 0 0 3"))
    )  # type: ignore
    expected_instructions = set(iter(stim.Circuit("H 0 1 2 3")))  # type: ignore
    assert (
        set(remove_duplicate_instructions(instructions, frozenset(["H"])))
        == expected_instructions
    )
    with pytest.warns(TQECWarning):
        # Several H gates are overlapping, which means that the returned instruction
        # list is not a valid Moment, which should raise a warning.
        assert remove_duplicate_instructions(instructions, frozenset()) == instructions

    instructions = list(iter(stim.Circuit("H 0 1 2 3 0 1 2 3\nM 4 5 6 4 5 6 4 5 6")))  # type: ignore
    with pytest.warns(TQECWarning):
        assert set(
            remove_duplicate_instructions(instructions, frozenset(["M"]))
        ) == set(iter(stim.Circuit("H 0 1 2 3 0 1 2 3\nM 4 5 6")))
    with pytest.warns(TQECWarning):
        assert set(
            remove_duplicate_instructions(instructions, frozenset(["H"]))
        ) == set(iter(stim.Circuit("H 0 1 2 3\nM 4 5 6 4 5 6 4 5 6")))
    assert set(
        remove_duplicate_instructions(instructions, frozenset(["H", "M"]))
    ) == set(iter(stim.Circuit("H 0 1 2 3\nM 4 5 6")))


def test_relabel_circuits_qubit_indices() -> None:
    # Any qubit target not defined by a QUBIT_COORDS instruction should raise
    # an exception.
    with pytest.raises(KeyError):
        relabel_circuits_qubit_indices(
            [
                ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2")),
                ScheduledCircuit.from_circuit(stim.Circuit("H 0 1 2")),
            ]
        )
    with pytest.raises(KeyError):
        relabel_circuits_qubit_indices(
            [
                ScheduledCircuit.from_circuit(
                    stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
                ),
                ScheduledCircuit.from_circuit(stim.Circuit("H 0")),
            ]
        )
    circuits, qubit_map = relabel_circuits_qubit_indices(
        [
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")),
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(1, 1) 0\nX 0")),
        ]
    )
    assert qubit_map == QubitMap({0: GridQubit(0, 0), 1: GridQubit(1, 1)})
    assert len(circuits) == 2
    assert circuits[0].get_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
    assert circuits[1].get_circuit() == stim.Circuit("QUBIT_COORDS(1, 1) 1\nX 1")


def test_relabel_circuits_qubit_indices_with_qubit_map() -> None:
    # With an explicit qubit map, that should be fine.
    qubit_map = QubitMap({20: GridQubit(0, 0), 15: GridQubit(1, 1)})
    circuits, qmap = relabel_circuits_qubit_indices(
        [
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")),
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(1, 1) 0\nX 0")),
        ],
        qubit_map=qubit_map,
    )
    assert qmap == qubit_map
    assert circuits[0].get_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 20\nH 20")
    assert circuits[1].get_circuit() == stim.Circuit("QUBIT_COORDS(1, 1) 15\nX 15")


def test_merge_scheduled_circuits() -> None:
    # Any qubit target not defined by a QUBIT_COORDS instruction should raise
    # an exception.
    _circuits, _qubit_map = relabel_circuits_qubit_indices(
        [
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")),
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(1, 1) 0\nX 0")),
        ]
    )
    circuit = merge_scheduled_circuits(_circuits, _qubit_map)
    assert circuit.get_circuit() == stim.Circuit(
        "QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 1) 1\nH 0\nX 1"
    )

    circuit = merge_scheduled_circuits(
        [
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")),
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")),
        ],
        global_qubit_map=QubitMap({0: GridQubit(0, 0)}),
        mergeable_instructions=["H"],
    )
    assert circuit.get_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")

    _circuits, _qubit_map = relabel_circuits_qubit_indices(
        [
            ScheduledCircuit.from_circuit(
                stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0\nTICK\nM 0"), [0, 2]
            ),
            ScheduledCircuit.from_circuit(stim.Circuit("QUBIT_COORDS(1, 1) 0\nX 0"), 1),
        ]
    )
    circuit = merge_scheduled_circuits(_circuits, _qubit_map)
    assert circuit.get_circuit() == stim.Circuit(
        "QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 1) 1\nH 0\nTICK\nX 1\nTICK\nM 0"
    )
