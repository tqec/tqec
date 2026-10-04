import pytest
import stim

from tqec.post_processing.shift import (
    circuit_bounding_box,
    scale_spatial_coordinates,
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


def test_scale_spatial_coordinates() -> None:
    circuit = stim.Circuit(
        """
        QUBIT_COORDS(2, 4) 0
        QUBIT_COORDS(6, 8) 1
        R 0 1
        SHIFT_COORDS(2, 2, 1)
        REPEAT 2 {
            CX 0 1
            M 1
            DETECTOR(4, 6, 3) rec[-1]
        }
        DETECTOR(4) rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
        """
    )
    expected = stim.Circuit(
        """
        QUBIT_COORDS(1, 2) 0
        QUBIT_COORDS(3, 4) 1
        R 0 1
        SHIFT_COORDS(1, 1, 1)
        REPEAT 2 {
            CX 0 1
            M 1
            DETECTOR(2, 3, 3) rec[-1]
        }
        DETECTOR(2) rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
        """
    )
    assert scale_spatial_coordinates(circuit, 0.5) == expected
    assert scale_spatial_coordinates(circuit, 1.0) == circuit
    assert scale_spatial_coordinates(scale_spatial_coordinates(circuit, 0.5), 2.0) == circuit
