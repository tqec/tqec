import numpy
import pytest
import stim

from tqec.compile.detectors.exact import (
    _deterministic_checks,
    _measurement_checks,
    _strip_annotations,
    annotate_detectors_exactly,
)
from tqec.compile.detectors.open_boundary import _OpenBoundaryAnalysis
from tqec.compile.detectors.space import GF2Basis


def detector_space(circuit: stim.Circuit) -> GF2Basis:
    return GF2Basis(c.measurements for c in _strip_annotations(circuit)[1])


def test_exact_annotation_removes_non_deterministic_candidate() -> None:
    annotated = annotate_detectors_exactly(stim.Circuit("RX 0\nM 0\nDETECTOR rec[-1]"))
    assert annotated.num_detectors == 0


@pytest.mark.parametrize("observable", ["", "OBSERVABLE_INCLUDE(0) rec[-2]"])
def test_repeated_logical_readout_is_only_one_syndrome(observable: str) -> None:
    circuit = stim.Circuit("R 0\nM 0\nM 0\nDETECTOR rec[-1]\n" + observable)
    analysis = _OpenBoundaryAnalysis(
        stim.Circuit("M 0\nM 0"), (1, 2), (stim.Flow("Z -> rec[0]"),), (1,)
    )
    annotated = annotate_detectors_exactly(circuit, analysis=analysis)
    assert detector_space(annotated).rows == (0b11,)
    assert not numpy.asarray(annotated.compile_detector_sampler().sample(32)).any()


def test_missing_semantics_only_filters_even_with_observables() -> None:
    circuit = stim.Circuit("R 0 1\nM 0 1\nDETECTOR rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-2]")
    annotated = annotate_detectors_exactly(circuit)
    assert detector_space(annotated).rows == (0b10,)


def test_explicit_empty_logical_semantics_completes() -> None:
    circuit = stim.Circuit("R 0 1\nM 0 1")
    analysis = _OpenBoundaryAnalysis(circuit, (1, 2), (), ())
    annotated = annotate_detectors_exactly(circuit, analysis=analysis)
    assert detector_space(annotated).rank == 2


def test_signed_checks_survive_elimination_and_completion() -> None:
    circuit = stim.Circuit("R 0\nM 0\nX 0\nM 0")
    checks, signs = _deterministic_checks(circuit)
    assert GF2Basis(checks).rank == 2
    assert any(signs)
    analysis = _OpenBoundaryAnalysis(
        stim.Circuit("M 0\nX 0\nM 0"), (1, 2), (stim.Flow("Z -> rec[0]"),), (1,)
    )
    annotated = annotate_detectors_exactly(circuit, analysis=analysis)
    assert detector_space(annotated).rows == (3,)
    assert not numpy.asarray(annotated.compile_detector_sampler().sample(32)).any()


@pytest.mark.parametrize(
    "analysis",
    [
        _OpenBoundaryAnalysis(stim.Circuit("MX 0\nM 0"), (1, 2), (stim.Flow("Z -> rec[0]"),), (1,)),
        _OpenBoundaryAnalysis(stim.Circuit("M 0\nM 0"), (1,), (), ()),
        _OpenBoundaryAnalysis(stim.Circuit("M 0"), (1,), (), ()),
        _OpenBoundaryAnalysis(stim.Circuit("M 0\nM 0"), (1, 2), (stim.Flow("Z -> -rec[0]"),), (1,)),
        _OpenBoundaryAnalysis(stim.Circuit("M 0\nM 0"), (1, 2), (stim.Flow("1 -> rec[0]"),), (1,)),
        _OpenBoundaryAnalysis(stim.Circuit("R 0\nM 0\nX 0\nM 0"), (0, 0), (), ()),
        _OpenBoundaryAnalysis(stim.Circuit("R 0\nM 0\nM 0"), (1, 4), (), ()),
    ],
)
def test_failed_semantics_never_completes(analysis) -> None:
    circuit = stim.Circuit("R 0\nM 0\nM 0\nDETECTOR rec[-1]")
    with pytest.warns(UserWarning, match="completion disabled"):
        annotated = annotate_detectors_exactly(circuit, analysis=analysis)
    assert detector_space(annotated).rows == (2,)


@pytest.mark.parametrize(
    "flows,sign",
    [
        (["Z -> Z xor rec[0]", "Z -> Z xor rec[1]"], 0),
        (["X -> X xor rec[0]", "Z -> Z xor rec[1]", "Y -> Y xor rec[2]"], 0),
        (["1 -> XX xor rec[0]", "1 -> ZZ xor rec[1]", "1 -> YY xor rec[2]"], 1),
    ],
)
def test_elimination_cancels_boundary_paulis_and_preserves_phases(flows, sign) -> None:
    checks, signs = _measurement_checks([stim.Flow(f) for f in flows], 2, len(flows))
    assert checks == ((1 << len(flows)) - 1,)
    assert signs == (sign,)
