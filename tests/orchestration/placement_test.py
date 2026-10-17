"""Regression tests for batch placement: relative positioning of components."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import stim

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.gallery.memory import memory
from tqec.orchestration import BatchConfig, UnitStatus, prepare_batch
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def stacked_l_shaped_corners() -> BlockGraph:
    """Two identical L-shaped memories, stacked at consecutive z, no pipe between.

    Reproduces issue #1062: a non-deterministic detector at k=1 across the
    boundary between two stacked spatial-junction corners.
    """
    g = BlockGraph("stacked_corners")
    for z in (0, 1):
        a, corner, b = Position3D(0, 1, z), Position3D(1, 1, z), Position3D(1, 0, z)
        g.add_cube(a, ZXCube.from_str("XZX"))
        g.add_cube(corner, ZXCube.from_str("ZZX"))
        g.add_cube(b, ZXCube.from_str("ZXX"))
        g.add_pipe(a, corner)
        g.add_pipe(corner, b)
    return g


def two_track_graph() -> BlockGraph:
    """Z memory with disconnected Hadamard track; reproduces issue #1063.

    Track A: Z memory; block (1,0,0) ends at z=0.
    Track B: disconnected track with Hadamard at z=1.

    When observables are passed explicitly, the observable of track A can become
    random if track B has a Hadamard at the same z where A ends.
    """
    g = BlockGraph("two_track")
    # Track A: Z memory
    g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ"))
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))

    # Track B: disconnected, with Hadamard at z=1
    g.add_cube(Position3D(3, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_cube(Position3D(3, 0, 1), ZXCube.from_str("XZX"))  # Hadamard
    g.add_pipe(Position3D(3, 0, 0), Position3D(3, 0, 1))

    return g


def sparse_z_graph() -> BlockGraph:
    """Two memories at z=0 and z=5 with no pipe; checks time gap handling.

    Sparse z slices (with gaps between components) crash to_layer_tree with
    "SequencedLayers expected at least one layer. Found 0."
    """
    g = BlockGraph("sparse_z")
    for z in (0, 5):
        g.add_cube(Position3D(0, 0, z), ZXCube.from_str("ZXZ"))
        g.add_cube(Position3D(1, 0, z), ZXCube.from_str("ZXZ"))
        g.add_pipe(Position3D(0, 0, z), Position3D(1, 0, z))
    return g


@pytest.mark.xfail(strict=False, reason="needs tqec#1088")
def test_stacked_l_shaped_memories_fixed_bulk(tmp_path: Path) -> None:
    """Test #1062 graph at k=1, fixed_bulk convention.

    Expected: one unit, one circuit, two observables mapped to two components,
    all detectors deterministic (currently fails due to non-deterministic detector).
    """
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), max_shots=100)
    manifest = prepare_batch([stacked_l_shaped_corners()], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == 1
    unit = ready[0]

    # One circuit for k=1
    assert 1 in unit.circuits
    assert manifest.run_dir is not None
    circuit_path = manifest.run_dir / unit.circuits[1]
    circuit = stim.Circuit(circuit_path.read_text())

    # Two logical observables (one per component)
    assert len(unit.logical_observables) == 2

    # All detectors should be deterministic in noiseless circuit
    det_samples_raw = circuit.compile_detector_sampler().sample(100)
    det_samples = np.array(det_samples_raw)
    assert float(det_samples.mean()) == 0.0, (
        f"Non-deterministic detector found: mean={det_samples.mean()}"
    )

    # Distance should be 3 at k=1 (test with noisy circuit)
    noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)
    distance = len(noisy.shortest_graphlike_error())
    assert distance == 3, f"Expected distance 3, got {distance}"


@pytest.mark.xfail(strict=False, reason="needs tqec#1088")
def test_stacked_l_shaped_memories_fixed_boundary(tmp_path: Path) -> None:
    """Test #1062 graph at k=1, fixed_boundary convention.

    Fixed-boundary variant of the same test, also currently fails.
    """
    config = BatchConfig(conventions=("fixed_boundary",), ks=(1,), max_shots=100)
    manifest = prepare_batch([stacked_l_shaped_corners()], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == 1
    unit = ready[0]

    assert 1 in unit.circuits
    assert manifest.run_dir is not None
    circuit_path = manifest.run_dir / unit.circuits[1]
    circuit = stim.Circuit(circuit_path.read_text())

    assert len(unit.logical_observables) == 2

    # All detectors should be deterministic in noiseless circuit
    det_samples_raw = circuit.compile_detector_sampler().sample(100)
    det_samples = np.array(det_samples_raw)
    assert float(det_samples.mean()) == 0.0, (
        f"Non-deterministic detector found: mean={det_samples.mean()}"
    )

    # Distance should be 3 at k=1 (test with noisy circuit)
    noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)
    distance = len(noisy.shortest_graphlike_error())
    assert distance == 3, f"Expected distance 3, got {distance}"


def test_two_track_deterministic_at_k1(tmp_path: Path) -> None:
    """Test #1063 graph: two-track with disconnected Hadamard at same z as track A end.

    Expected: one circuit, every observable deterministic, distance 3 at k=1.
    The full graph with both tracks should have observables that don't span components.
    """
    graph = two_track_graph()

    config = BatchConfig(
        conventions=("fixed_bulk",), ks=(1,), max_shots=100, logical_observables="all"
    )
    manifest = prepare_batch([graph], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == 1, "Two-track graph should yield one unit"
    unit = ready[0]

    assert 1 in unit.circuits
    assert manifest.run_dir is not None
    circuit_path = manifest.run_dir / unit.circuits[1]
    circuit = stim.Circuit(circuit_path.read_text())

    # All observables should be deterministic in a noiseless circuit
    _, obs = circuit.compile_detector_sampler().sample(100, separate_observables=True)
    obs_array = np.array(obs)
    for i, observable in enumerate(obs_array):
        # Each observable should be either all 0 or all 1 (deterministic)
        mean_val = float(observable.mean())
        assert mean_val in (0.0, 1.0), f"Observable {i} is non-deterministic: mean={mean_val}"

    # Distance should be 3 at k=1 (test with noisy circuit)
    noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)
    distance = len(noisy.shortest_graphlike_error())
    assert distance == 3, f"Expected distance 3, got {distance}"


def test_sparse_z_gap_crash(tmp_path: Path) -> None:
    """Test sparse z: two memories at z=0 and z=5 with gap in between.

    Sparse z slices (with gaps between components) crash to_layer_tree with
    "SequencedLayers expected at least one layer. Found 0." The error is caught
    and recorded as a circuit failure. This is expected until SHIFT_COORDS policy
    is settled.
    """
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), max_shots=100)
    manifest = prepare_batch([sparse_z_graph()], config, tmp_path / "run")

    # The unit should fail at the circuit stage with TQECError
    units = manifest.units
    assert len(units) == 1
    unit = units[0]
    assert unit.terminal, "Sparse z graph should produce a terminal failure"
    assert unit.stage == "circuit", f"Expected failure at circuit stage, got stage={unit.stage}"
    assert "SequencedLayers" in unit.notes, f"Expected 'SequencedLayers' error, got: {unit.notes}"
    assert unit.error == "TQECError", f"Expected TQECError, got error={unit.error}"


def test_split_components_yields_multiple_units_same_device_frame(tmp_path: Path) -> None:
    """Test split_components=True gives N units with same device_frame (contract item 4).

    Uses a BlockGraph with multiple components and split_components=True.
    Expects one unit per component, each with the same device_frame.
    """
    graph = stacked_l_shaped_corners()
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), max_shots=100, split_components=True)
    manifest = prepare_batch([graph], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    # Two L-shaped memories should yield 2 units when split
    assert len(ready) == 2

    # All units should have the same device_frame
    device_frames = [u.device_frame for u in ready]
    assert all(df == device_frames[0] for df in device_frames), (
        f"Device frames should be identical in split mode, got: {device_frames}"
    )
    # device_frame should contain minimum and maximum
    assert device_frames[0] is not None
    assert "minimum" in device_frames[0]
    assert "maximum" in device_frames[0]


def test_manifest_fields_device_frame_and_components(tmp_path: Path) -> None:
    """Test manifest fields from contract item 3 are present and consistent.

    Monolithic mode (default): one unit with device_frame, components list,
    and observable_components mapping observables to component ids.
    """
    graph = stacked_l_shaped_corners()
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), max_shots=100)
    manifest = prepare_batch([graph], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == 1, "Default mode should yield one unit per input"
    unit = ready[0]

    # Verify device_frame: AABB of whole input graph
    assert unit.device_frame is not None, "device_frame should be present"
    assert "minimum" in unit.device_frame
    assert "maximum" in unit.device_frame
    device_min = unit.device_frame["minimum"]
    device_max = unit.device_frame["maximum"]
    assert isinstance(device_min, list) and len(device_min) == 3
    assert isinstance(device_max, list) and len(device_max) == 3

    # Verify components: list of component IDs and bounds
    assert unit.components is not None, "components should be present"
    assert isinstance(unit.components, list)
    assert len(unit.components) >= 2, "stacked_l_shaped_corners has 2 components"

    # Each component should have component_id, minimum, maximum
    component_ids = []
    for component in unit.components:
        assert "component_id" in component, f"component missing component_id: {component}"
        assert "minimum" in component, f"component missing minimum: {component}"
        assert "maximum" in component, f"component missing maximum: {component}"
        component_ids.append(component["component_id"])

    # Components should be named c00, c01, ... in order
    expected_ids = [f"c{i:02d}" for i in range(len(unit.components))]
    assert component_ids == expected_ids, (
        f"Component ids should be {expected_ids}, got {component_ids}"
    )

    # Verify observable_components: mapping observables to component ids
    assert unit.observable_components is not None, "observable_components should be present"
    assert isinstance(unit.observable_components, list)
    num_observables = len(unit.logical_observables)
    assert len(unit.observable_components) == num_observables, (
        f"observable_components length {len(unit.observable_components)} "
        f"should match observables {num_observables}"
    )

    # Each observable should map to a valid component
    for i, component_id in enumerate(unit.observable_components):
        assert component_id in component_ids, (
            f"Observable {i} maps to {component_id}, not in {component_ids}"
        )


def test_memory_gadgets_as_baseline(tmp_path: Path) -> None:
    """Baseline test with simple memory gadgets for reference.

    This test ensures our test infrastructure works correctly.
    """
    config = BatchConfig(conventions=("fixed_bulk",), ks=(1,), max_shots=100)
    manifest = prepare_batch([memory(Basis.Z)], config, tmp_path / "run")

    ready = [u for u in manifest.units if u.status == UnitStatus.READY.value]
    assert len(ready) == 1
    unit = ready[0]

    assert 1 in unit.circuits
    assert manifest.run_dir is not None
    circuit_path = manifest.run_dir / unit.circuits[1]
    circuit = stim.Circuit(circuit_path.read_text())

    # A simple Z memory should have one logical observable
    assert len(unit.logical_observables) >= 1

    # All detectors should be deterministic in noiseless circuit
    det_samples_raw = circuit.compile_detector_sampler().sample(100)
    det_samples = np.array(det_samples_raw)
    assert float(det_samples.mean()) == 0.0
