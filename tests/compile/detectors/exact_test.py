import stim

from tqec.compile.detectors.exact import annotate_detectors_exactly


def test_exact_annotation_removes_non_deterministic_candidate() -> None:
    circuit = stim.Circuit(
        """
        RX 0
        M 0
        DETECTOR rec[-1]
        """
    )

    annotated = annotate_detectors_exactly(circuit)

    assert annotated.num_detectors == 0
    annotated.detector_error_model(allow_gauge_detectors=False)


def test_exact_annotation_completes_deterministic_relation_space() -> None:
    circuit = stim.Circuit(
        """
        R 0 1
        M 0 1
        DETECTOR rec[-2]
        """
    )

    annotated = annotate_detectors_exactly(circuit)

    assert annotated.num_detectors == 2
    annotated.detector_error_model(allow_gauge_detectors=False)


def test_exact_annotation_does_not_turn_observable_into_detector() -> None:
    circuit = stim.Circuit(
        """
        R 0 1
        M 0 1
        OBSERVABLE_INCLUDE(0) rec[-2]
        """
    )

    annotated = annotate_detectors_exactly(circuit)

    assert annotated.num_detectors == 1
    assert annotated.num_observables == 1
