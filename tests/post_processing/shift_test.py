import pytest
import stim

from tqec.post_processing.shift import (
    circuit_bounding_box,
    shift_qubits,
    shift_to_only_positive,
)


@pytest.mark.parametrize("circuit", [stim.Circuit(), stim.Circuit("H 0")])
def test_circuit_bounding_box_without_qubit_coordinates(
    circuit: stim.Circuit,
) -> None:
    assert circuit_bounding_box(circuit) == ([], [])


def test_shift_to_only_positive_without_qubit_coordinates() -> None:
    circuit = stim.Circuit("H 0")
    assert shift_to_only_positive(circuit) == circuit


def test_shift_qubits_shifts_detector_coordinates() -> None:
    circuit = stim.Circuit(
        """
        QUBIT_COORDS(1, 2) 0
        DETECTOR(3, 4) rec[-1]
        """
    )

    shifted = shift_qubits(circuit, 10, 20)

    assert shifted == stim.Circuit(
        """
        QUBIT_COORDS(11, 22) 0
        DETECTOR(13, 24) rec[-1]
        """
    )


def test_shift_qubits_shifts_repeat_block() -> None:
    circuit = stim.Circuit(
        """
        REPEAT 2 {
            QUBIT_COORDS(1, 2) 0
        }
        """
    )

    shifted = shift_qubits(circuit, 10, 20)

    assert shifted == stim.Circuit(
        """
        REPEAT 2 {
            QUBIT_COORDS(11, 22) 0
        }
        """
    )


def test_circuit_bounding_box_with_qubit_coordinates() -> None:
    circuit = stim.Circuit(
        """
        QUBIT_COORDS(1, 5) 0
        QUBIT_COORDS(-2, 9) 1
        QUBIT_COORDS(4, 3) 2
        """
    )

    assert circuit_bounding_box(circuit) == ([-2, 3], [4, 9])