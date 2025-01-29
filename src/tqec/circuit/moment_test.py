import pytest
import stim

from tqec.circuit.moment import Moment, iter_stim_circuit_without_repeat_by_moments
from tqec.utils.exceptions import TQECException

_VALID_MOMENT_CIRCUITS: list[stim.Circuit] = [
    stim.Circuit("H 0 1 2 3"),
    stim.Circuit("M 1 4 6"),
    stim.Circuit("CX 0 1 2 3 4 5"),
    stim.Circuit("H 0 3\nM 1 2 4"),
    stim.Circuit("H 0\nQUBIT_COORDS(0, 0) 0"),
    stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0"),
]
_INVALID_MOMENT_CIRCUITS: list[stim.Circuit] = [
    stim.Circuit("H 0 0"),
    stim.Circuit("M 1 1"),
    stim.Circuit("CX 0 1 1 2"),
    stim.Circuit("H 0 3\nM 0 4"),
    stim.Circuit("R 0\nM 0"),
    stim.Circuit("TICK"),
    stim.Circuit("REPEAT 2 {\n    H 0\n}"),
]


@pytest.mark.parametrize("circuit", _VALID_MOMENT_CIRCUITS)
def test_moment_creation(circuit: stim.Circuit) -> None:
    Moment(circuit)


@pytest.mark.parametrize("circuit", _INVALID_MOMENT_CIRCUITS)
def test_moment_invalid_creation(circuit: stim.Circuit) -> None:
    with pytest.raises(TQECException):
        Moment(circuit)


@pytest.mark.parametrize("circuit", _VALID_MOMENT_CIRCUITS)
def test_moment_circuit_property(circuit: stim.Circuit) -> None:
    assert Moment(circuit).circuit == circuit


def test_moment_is_empty() -> None:
    assert Moment(stim.Circuit()).is_empty
    assert not Moment(stim.Circuit("H 0")).is_empty
    assert not Moment(stim.Circuit("DETECTOR(0, 0, 1) rec[-1]")).is_empty


def test_moment_qubit_indices() -> None:
    assert Moment(stim.Circuit("H 0 1 2 3")).qubits_indices == frozenset([0, 1, 2, 3])
    assert Moment(stim.Circuit("M 1 4 6")).qubits_indices == frozenset([1, 4, 6])
    assert Moment(stim.Circuit("CX 0 1 2 3 4 5")).qubits_indices == frozenset(
        [0, 1, 2, 3, 4, 5]
    )
    assert Moment(stim.Circuit("H 0 3\nM 1 2 4")).qubits_indices == frozenset(
        [0, 1, 2, 3, 4]
    )
    assert Moment(
        stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
    ).qubits_indices == frozenset([0])


def test_moment_contains_instruction() -> None:
    assert Moment(stim.Circuit("H 0 1 2 3")).contains_instruction("H")
    assert not Moment(stim.Circuit("H 0 1 2 3")).contains_instruction("M")
    assert Moment(stim.Circuit("M 1 4 6")).contains_instruction("M")
    assert not Moment(stim.Circuit("MX 1 4 6")).contains_instruction("M")
    assert Moment(stim.Circuit("MX 1 4 6")).contains_instruction("MX")
    assert Moment(stim.Circuit("CX 0 1 2 3 4 5")).contains_instruction("CX")
    assert Moment(stim.Circuit("H 0 3\nM 1 2 4")).contains_instruction("H")
    assert Moment(stim.Circuit("H 0 3\nM 1 2 4")).contains_instruction("M")
    assert Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")).contains_instruction("H")
    assert Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")).contains_instruction(
        "QUBIT_COORDS"
    )


def test_moment_remove_all_instructions_inplace() -> None:
    moment = Moment(stim.Circuit("H 0 1 2 3"))
    assert moment.contains_instruction("H")
    moment.remove_all_instructions_inplace(frozenset(["M"]))
    assert moment.contains_instruction("H")
    moment.remove_all_instructions_inplace(frozenset(["H"]))
    assert not moment.contains_instruction("H")

    moment = Moment(stim.Circuit("H 0 3\nM 1 2 4\nH 5"))
    assert moment.contains_instruction("H")
    assert moment.contains_instruction("M")
    moment.remove_all_instructions_inplace(frozenset(["H"]))
    assert not moment.contains_instruction("H")
    assert moment.contains_instruction("M")

    moment = Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0"))
    assert moment.contains_instruction("H")
    assert moment.contains_instruction("QUBIT_COORDS")
    moment.remove_all_instructions_inplace(frozenset(["H", "QUBIT_COORDS"]))
    assert not moment.contains_instruction("H")
    assert not moment.contains_instruction("QUBIT_COORDS")
    assert moment.circuit == stim.Circuit()


def test_moment_iadd() -> None:
    moment = Moment(stim.Circuit("H 0"))
    moment += Moment(stim.Circuit("H 1"))
    moment += Moment(stim.Circuit("H 2"))
    assert moment.circuit == stim.Circuit("H 0 1 2")
    moment += Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0"))
    assert moment.circuit == stim.Circuit("H 0 1 2\nQUBIT_COORDS(0, 0) 0")

    with pytest.raises(
        TQECException,
        match="^Trying to add an overlapping quantum circuit to a Moment instance.$",
    ):
        moment += Moment(stim.Circuit("H 0"))


def test_moment_append() -> None:
    moment = Moment(stim.Circuit("H 0"))
    moment.append("H", [stim.GateTarget(1)], [])
    moment.append("H", [stim.GateTarget(2)], [])
    assert moment.circuit == stim.Circuit("H 0 1 2")
    moment.append("QUBIT_COORDS", [stim.GateTarget(0)], [0, 0])
    assert moment.circuit == stim.Circuit("H 0 1 2\nQUBIT_COORDS(0, 0) 0")

    with pytest.raises(
        TQECException,
        match=r"^Cannot add H 0 to the Moment due to qubit\(s\) \{0\} being already in use.$",
    ):
        moment.append("H", [stim.GateTarget(0)], [])


def test_moment_append_instruction() -> None:
    moment = Moment(stim.Circuit("H 0"))
    moment.append(stim.CircuitInstruction("H", [stim.GateTarget(1)], []))
    moment.append(stim.CircuitInstruction("H", [stim.GateTarget(2)], []))
    assert moment.circuit == stim.Circuit("H 0 1 2")
    moment.append(stim.CircuitInstruction("QUBIT_COORDS", [stim.GateTarget(0)], [0, 0]))
    assert moment.circuit == stim.Circuit("H 0 1 2\nQUBIT_COORDS(0, 0) 0")

    with pytest.raises(
        TQECException,
        match=r"^Cannot add H 0 to the Moment due to qubit\(s\) \{0\} being already in use.$",
    ):
        moment.append(stim.CircuitInstruction("H", [stim.GateTarget(0)], []))


def test_moment_append_annotation() -> None:
    moment = Moment(stim.Circuit("H 0"))
    moment.append_annotation(
        stim.CircuitInstruction("DETECTOR", [stim.target_rec(-1)], [0, 0, 1])
    )
    moment.append_annotation(
        stim.CircuitInstruction("OBSERVABLE_INCLUDE", [stim.target_rec(-1)], [1])
    )
    assert moment.circuit == stim.Circuit(
        "H 0\nDETECTOR(0, 0, 1) rec[-1]\nOBSERVABLE_INCLUDE(1) rec[-1]"
    )
    with pytest.raises(
        TQECException,
        match="^The method append_annotation only supports appending annotations.*",
    ):
        moment.append_annotation(stim.CircuitInstruction("H", [stim.GateTarget(0)], []))


@pytest.mark.parametrize("circuit", _VALID_MOMENT_CIRCUITS)
def test_moment_instructions_property(circuit: stim.Circuit) -> None:
    assert list(Moment(circuit).instructions) == list(iter(circuit))


def test_moment_num_measurements() -> None:
    assert Moment(stim.Circuit("H 0 1 2 3")).num_measurements == 0
    assert Moment(stim.Circuit("M 1 4 6")).num_measurements == 3
    assert Moment(stim.Circuit("MX 1 4 6")).num_measurements == 3
    assert Moment(stim.Circuit("CX 0 1 2 3 4 5")).num_measurements == 0
    assert Moment(stim.Circuit("H 0 3\nM 1 2 4")).num_measurements == 3
    assert Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")).num_measurements == 0


def test_moment_filter_by_qubits() -> None:
    fqs = [0, 2, 4, 5, 6, 789345]
    assert Moment(stim.Circuit("H 0 1 2 3")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("H 0 2")
    assert Moment(stim.Circuit("M 1 4 6")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("M 4 6")
    assert Moment(stim.Circuit("MX 1 4 6")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("MX 4 6")
    assert Moment(stim.Circuit("CX 0 1 2 3 4 5")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("CX 4 5")
    assert Moment(stim.Circuit("H 0 3\nM 1 2 4")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("H 0\nM 2 4")
    assert Moment(stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")).filter_by_qubits(
        fqs
    ).circuit == stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")


@pytest.mark.parametrize("circuit", _VALID_MOMENT_CIRCUITS)
def test_iterate_circuit_by_moment_simple(circuit: stim.Circuit) -> None:
    moments = list(iter_stim_circuit_without_repeat_by_moments(circuit))
    assert len(moments) == 1
    assert moments[0].circuit == circuit


def test_iterate_circuit_by_moment() -> None:
    moments = list(
        iter_stim_circuit_without_repeat_by_moments(stim.Circuit("TICK\nTICK\nTICK"))
    )
    assert len(moments) == 4
    for moment in moments:
        assert moment.circuit == stim.Circuit()

    moments = list(
        iter_stim_circuit_without_repeat_by_moments(
            stim.Circuit("H 0 1 2 3\nTICK\nH 0 1 2 3")
        )
    )
    assert len(moments) == 2
    for moment in moments:
        assert moment.circuit == stim.Circuit("H 0 1 2 3")

    with pytest.raises(TQECException):
        list(
            iter_stim_circuit_without_repeat_by_moments(
                stim.Circuit("H 0 1 2 3\nH 0 1 2 3\nTICK\nH 0 1 2 3")
            )
        )

    with pytest.raises(TQECException):
        list(
            iter_stim_circuit_without_repeat_by_moments(
                stim.Circuit("REPEAT 10 {\n    H 0 1 2 3\n}")
            )
        )


def test_moment_with_mapped_qubit_indices() -> None:
    moment = Moment(
        stim.Circuit(
            "QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(0, 1) 1\nH 0 1\nDETECTOR(0, 0) rec[-1]"
        )
    )
    mapped_moment = moment.with_mapped_qubit_indices({0: 1, 1: 0})
    assert mapped_moment.circuit == stim.Circuit(
        "QUBIT_COORDS(0, 0) 1\nQUBIT_COORDS(0, 1) 0\nH 1 0\nDETECTOR(0, 0) rec[-1]"
    )
    assert mapped_moment.qubits_indices == {0, 1}
    assert moment.circuit == stim.Circuit(
        "QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(0, 1) 1\nH 0 1\nDETECTOR(0, 0) rec[-1]"
    )
    mapped_moment = moment.with_mapped_qubit_indices({0: 12, 1: 56, 2: 23})
    assert mapped_moment.circuit == stim.Circuit(
        "QUBIT_COORDS(0, 0) 12\nQUBIT_COORDS(0, 1) 56\nH 12 56\nDETECTOR(0, 0) rec[-1]"
    )
    assert mapped_moment.qubits_indices == {12, 56}
