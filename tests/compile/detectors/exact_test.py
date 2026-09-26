import numpy
import pytest
import stim

from tqec.compile.detectors.exact import (
    _deterministic_checks,
    _strip_annotations,
    _syndrome_space,
    annotate_detectors_exactly,
)
from tqec.compile.detectors.space import GF2Basis


def detector_space(circuit: stim.Circuit) -> GF2Basis:
    return GF2Basis(c.measurements for c in _strip_annotations(circuit)[1])


def test_exact_annotation_removes_non_deterministic_candidate() -> None:
    annotated = annotate_detectors_exactly(stim.Circuit("RX 0\nM 0\nDETECTOR rec[-1]"))
    assert annotated.num_detectors == 0


@pytest.mark.parametrize("observable", ["", "OBSERVABLE_INCLUDE(0) rec[-2]"])
def test_repeated_logical_readout_is_only_one_syndrome(observable: str) -> None:
    circuit = stim.Circuit("R 0\nM 0\nM 0\nDETECTOR rec[-1]\n" + observable)
    perturbed = stim.Circuit("R 0\nX 0\nM 0\nM 0")
    annotated = annotate_detectors_exactly(
        circuit, logical_perturbations=[perturbed], logical_supports=[1]
    )
    assert detector_space(annotated).rows == (0b11,)
    assert not numpy.asarray(annotated.compile_detector_sampler().sample(32)).any()


def test_missing_semantics_only_filters_even_with_observables() -> None:
    circuit = stim.Circuit("R 0 1\nM 0 1\nDETECTOR rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-2]")
    annotated = annotate_detectors_exactly(circuit)
    assert detector_space(annotated).rows == (0b10,)


def test_explicit_empty_logical_semantics_completes() -> None:
    circuit = stim.Circuit("R 0 1\nM 0 1")
    annotated = annotate_detectors_exactly(circuit, logical_perturbations=[], logical_supports=[])
    assert detector_space(annotated).rank == 2


def test_signed_checks_survive_elimination_and_completion() -> None:
    circuit = stim.Circuit("R 0\nX 0\nM 0\nM 0")
    checks, signs = _deterministic_checks(circuit)
    assert GF2Basis(checks).rank == 2
    assert any(signs)
    perturbed = stim.Circuit("R 0\nX 0\nX 0\nM 0\nM 0")
    annotated = annotate_detectors_exactly(
        circuit, logical_perturbations=[perturbed], logical_supports=[1]
    )
    assert detector_space(annotated).rows == (3,)
    # A negative deterministic parity is still a valid detector: Stim uses its
    # reference sample, not an assumption that every ideal measurement is zero.
    negative = annotate_detectors_exactly(
        stim.Circuit("R 0\nX 0\nM 0"), logical_perturbations=[], logical_supports=[]
    )
    assert negative.num_detectors == 1
    assert not numpy.asarray(negative.compile_detector_sampler().sample(32)).any()


@pytest.mark.parametrize(
    "perturbations,supports",
    [
        ([stim.Circuit("RX 0\nM 0\nM 0")], [1]),
        ([stim.Circuit("R 0\nM 0\nM 0")], [1]),
        ([], [1]),
        ([stim.Circuit("R 0\nM 0")], [1]),
        ([stim.Circuit("R 0\nX 0\nM 0\nM 0")], [4]),
    ],
)
def test_failed_semantics_never_completes(perturbations, supports) -> None:
    circuit = stim.Circuit("R 0\nM 0\nM 0\nDETECTOR rec[-1]")
    with pytest.warns(UserWarning, match="completion disabled"):
        annotated = annotate_detectors_exactly(
            circuit, logical_perturbations=perturbations, logical_supports=supports
        )
    assert detector_space(annotated).rows == (2,)


def test_response_kernel_combines_multiple_logical_checks() -> None:
    circuit = stim.Circuit("R 0 1\nM 0 1\nM 0 1")
    perturbations = [stim.Circuit(f"R 0 1\nX {q}\nM 0 1\nM 0 1") for q in range(2)]
    checks, signs = _deterministic_checks(circuit)
    syndrome = _syndrome_space(circuit, checks, signs, perturbations, [1, 2])
    assert syndrome.rank == 2
    assert syndrome.contains(0b0101)
    assert syndrome.contains(0b1010)
