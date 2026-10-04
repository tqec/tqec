import pytest
import stim

from tqec.post_processing.shift import (
    circuit_bounding_box,
    shift_to_only_positive,
    transform_spatial_coordinates,
)


@pytest.mark.parametrize("circuit", [stim.Circuit(), stim.Circuit("H 0")])
def test_circuit_bounding_box_without_qubit_coordinates(
    circuit: stim.Circuit,
) -> None:
    assert circuit_bounding_box(circuit) == ([], [])


def test_shift_to_only_positive_without_qubit_coordinates() -> None:
    circuit = stim.Circuit("H 0")
    assert shift_to_only_positive(circuit) == circuit


_CIRCUIT = stim.Circuit(
    """
    QUBIT_COORDS(2, 4) 0
    QUBIT_COORDS(6, 8) 1
    R 0 1
    SHIFT_COORDS(2, 2, 1)
    REPEAT 2 {
        CX 0 1
        M 1
        DETECTOR(4, 6, 3) rec[-1]
        SHIFT_COORDS(0, 2, 1)
    }
    DETECTOR(4) rec[-1]
    OBSERVABLE_INCLUDE(0) rec[-1]
    """
)


def test_transform_spatial_coordinates_scale_only() -> None:
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
            SHIFT_COORDS(0, 1, 1)
        }
        DETECTOR(2) rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
        """
    )
    assert transform_spatial_coordinates(_CIRCUIT, 0.5) == expected
    assert transform_spatial_coordinates(_CIRCUIT) == _CIRCUIT
    assert (
        transform_spatial_coordinates(transform_spatial_coordinates(_CIRCUIT, 0.5), 2.0) == _CIRCUIT
    )


def test_transform_spatial_coordinates_offset_is_not_applied_to_shifts() -> None:
    expected = stim.Circuit(
        """
        QUBIT_COORDS(2, -1) 0
        QUBIT_COORDS(4, 1) 1
        R 0 1
        SHIFT_COORDS(1, 1, 1)
        REPEAT 2 {
            CX 0 1
            M 1
            DETECTOR(3, 0, 3) rec[-1]
            SHIFT_COORDS(0, 1, 1)
        }
        DETECTOR(3) rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
        """
    )
    assert transform_spatial_coordinates(_CIRCUIT, 0.5, (1, -3)) == expected


@pytest.mark.parametrize(
    ("scale", "offset"), [(0.5, (0.0, 0.0)), (0.5, (1.0, -3.0)), (2.0, (0.5, 0.25))]
)
def test_transform_spatial_coordinates_maps_absolute_coordinates(
    scale: float, offset: tuple[float, float]
) -> None:
    def affine(coords: list[float]) -> list[float]:
        return [c * scale + offset[i] if i < 2 else c for i, c in enumerate(coords)]

    transformed = transform_spatial_coordinates(_CIRCUIT, scale, offset)
    assert transformed.get_final_qubit_coordinates() == {
        q: affine(c) for q, c in _CIRCUIT.get_final_qubit_coordinates().items()
    }
    detectors = _CIRCUIT.get_detector_coordinates()
    assert len(detectors) == 3
    assert transformed.get_detector_coordinates() == {d: affine(c) for d, c in detectors.items()}
