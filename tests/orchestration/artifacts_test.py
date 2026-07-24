"""Tests for :mod:`tqec.orchestration.artifacts`--the circuit-writer seam."""

from __future__ import annotations

from pathlib import Path

import pytest
import stim

from tqec.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.gallery.memory import memory
from tqec.orchestration import BatchManifest, UnitStatus, prepare_batch
from tqec.orchestration.artifacts import write_circuit
from tqec.orchestration.models import BatchConfig
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError


def _compiled_memory():
    """Compile a small closed memory gadget under the fixed-bulk convention."""
    return compile_block_graph(memory(Basis.Z), FIXED_BULK_CONVENTION)


def test_streaming_matches_materialized_bytes_and_circuit(tmp_path: Path) -> None:
    # For all deterministic gadgets, treamed circuit generation mode must never
    # change the materialized circuit. This test verfies that the on-disk
    # file equal the materialized output both as a parsed circuit and
    # byte-for-byte.
    compiled = _compiled_memory()
    materialized_path = tmp_path / "mat.stim"
    streaming_path = tmp_path / "stream.stim"

    write_circuit(
        compiled, 1, materialized_path, mode="materialized", manhattan_radius=2
    )
    write_circuit(compiled, 1, streaming_path, mode="streaming", manhattan_radius=2)

    assert stim.Circuit.from_file(materialized_path) == stim.Circuit.from_file(
        streaming_path
    )
    assert materialized_path.read_bytes() == streaming_path.read_bytes()


def test_materialized_matches_direct_generate(tmp_path: Path) -> None:
    # Materialized mode must be byte-for-byte the usual behaviour: generate then to_file.
    compiled = _compiled_memory()
    direct_path = tmp_path / "direct.stim"
    compiled.generate_stim_circuit(1, manhattan_radius=2).to_file(direct_path)

    seam_path = tmp_path / "seam.stim"
    write_circuit(compiled, 1, seam_path, mode="materialized", manhattan_radius=2)

    assert direct_path.read_bytes() == seam_path.read_bytes()


def test_write_circuit_rejects_unknown_mode(tmp_path: Path) -> None:
    compiled = _compiled_memory()
    with pytest.raises(ValueError, match="Unknown circuit mode"):
        write_circuit(compiled, 1, tmp_path / "x.stim", mode="nope", manhattan_radius=2)


def test_batch_config_validates_circuit_mode() -> None:
    BatchConfig(circuit_mode="materialized").validate()
    BatchConfig(circuit_mode="streaming").validate()
    with pytest.raises(TQECError, match="circuit_mode"):
        BatchConfig(circuit_mode="bogus").validate()


def test_batch_config_round_trips_circuit_mode() -> None:
    config = BatchConfig(circuit_mode="streaming")
    assert config.to_dict()["circuit_mode"] == "streaming"
    assert BatchConfig.from_dict(config.to_dict()).circuit_mode == "streaming"
    # A legacy manifest with no circuit_mode key falls back to the materialized default.
    legacy = {k: v for k, v in config.to_dict().items() if k != "circuit_mode"}
    assert BatchConfig.from_dict(legacy).circuit_mode == "materialized"


def _ready_circuit_bytes(manifest: BatchManifest) -> bytes:
    """Return the k=1 circuit bytes of the single READY unit in a manifest."""
    assert manifest.run_dir is not None
    ready = next(u for u in manifest.units if u.status == UnitStatus.READY.value)
    return (manifest.run_dir / ready.circuits[1]).read_bytes()


def test_prepare_streaming_mode_matches_materialized(tmp_path: Path) -> None:
    # End-to-end: preparing the same gadget under each circuit_mode leaves identical .stim bytes.
    mat_config = BatchConfig(
        conventions=("fixed_bulk",),
        ks=(1,),
        observables="auto",
        circuit_mode="materialized",
    )
    stream_config = BatchConfig(
        conventions=("fixed_bulk",),
        ks=(1,),
        observables="auto",
        circuit_mode="streaming",
    )
    mat = prepare_batch([memory(Basis.Z)], mat_config, tmp_path / "mat")
    stream = prepare_batch([memory(Basis.Z)], stream_config, tmp_path / "stream")

    assert _ready_circuit_bytes(mat) == _ready_circuit_bytes(stream)
