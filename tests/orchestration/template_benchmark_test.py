"""End-to-end compile-benchmark over the ``template.dae`` asset.

This exercises the whole batch workflow the template asset is designed for: split one DAE that
holds every computational primitive, auto-fill open ports, and record a per-primitive compile
outcome in a single run. It benchmarks *whether each block compiles* -- distinct from
fault-tolerance/threshold checking -- so the assertions lock the outcome mix, not any error rate.

The mix was characterized empirically (not guessed) against ``assets/template.dae``: 23 components
-> 6 compile (``READY``), 12 pure open-port placeholders ``SKIPPED``, 1 invalid graph (a Y half
cube with no connecting pipe), and 4 un-importable placeholder swatches (a bare pipe, a standalone
``P`` port marker, and two ``T``-basis swatches). The point is that the workflow completes
gracefully -- every placeholder swatch is recorded as a terminal failure or skip, never crashing
the batch -- while still yielding compiled primitives.
"""

from __future__ import annotations

import collections
from pathlib import Path

import pytest

from tqec.orchestration.models import BatchConfig, BatchManifest, UnitStatus
from tqec.orchestration.prepare import prepare_batch

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"

# Locked outcome mix, characterized against assets/template.dae (see module docstring).
_EXPECTED_TOTAL = 23
_EXPECTED_READY = 6
_EXPECTED_SKIPPED = 12
_EXPECTED_INVALID = 1
_EXPECTED_IMPORT_FAILED = 4


@pytest.fixture(scope="module")
def template_manifest(tmp_path_factory: pytest.TempPathFactory) -> BatchManifest:
    """Prepare the template benchmark once and share the manifest across the module's tests."""
    config = BatchConfig(
        conventions=("fixed_bulk",), ks=(1,), observables="minimal", max_shots=100
    )
    out = tmp_path_factory.mktemp("template_benchmark")
    return prepare_batch([ASSETS_DIR / "template.dae"], config, out)


def test_benchmark_completes_over_every_primitive(template_manifest: BatchManifest) -> None:
    # Every component is accounted for -- a bad swatch never aborts the run.
    assert len(template_manifest.units) == _EXPECTED_TOTAL


def test_outcome_mix_is_locked(template_manifest: BatchManifest) -> None:
    counts = collections.Counter(u.status for u in template_manifest.units)
    assert counts[UnitStatus.READY.value] == _EXPECTED_READY
    assert counts[UnitStatus.SKIPPED.value] == _EXPECTED_SKIPPED
    assert counts[UnitStatus.INVALID_GRAPH.value] == _EXPECTED_INVALID
    assert counts[UnitStatus.IMPORT_FAILED.value] == _EXPECTED_IMPORT_FAILED


def test_ready_units_have_generated_circuits(template_manifest: BatchManifest) -> None:
    ready = [u for u in template_manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == _EXPECTED_READY
    for unit in ready:
        assert unit.circuits and 1 in unit.circuits


def test_port_placeholders_are_skipped_not_failed(template_manifest: BatchManifest) -> None:
    skipped = [u for u in template_manifest.units if u.status == UnitStatus.SKIPPED.value]
    assert len(skipped) == _EXPECTED_SKIPPED
    for unit in skipped:
        assert "port" in unit.notes.lower()


def test_unimportable_swatches_keep_their_real_error_type(template_manifest: BatchManifest) -> None:
    failed = [u for u in template_manifest.units if u.status == UnitStatus.IMPORT_FAILED.value]
    assert len(failed) == _EXPECTED_IMPORT_FAILED
    # The real exception type is preserved, not a hardcoded ImportError: the "P"/"T" swatches
    # surface as ValueError and the bare pipe as TQECError.
    errors = {u.error for u in failed}
    assert "ValueError" in errors
    assert "TQECError" in errors
