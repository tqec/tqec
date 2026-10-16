import pytest
import stim

from tqec.post_processing.shift import circuit_bounding_box, shift_to_only_positive


@pytest.mark.parametrize("circuit", [stim.Circuit(), stim.Circuit("H 0")])
def test_circuit_bounding_box_without_qubit_coordinates(
    circuit: stim.Circuit,
) -> None:
    assert circuit_bounding_box(circuit) == ([], [])


def test_shift_to_only_positive_without_qubit_coordinates() -> None:
    circuit = stim.Circuit("H 0")
    assert shift_to_only_positive(circuit) == circuit
