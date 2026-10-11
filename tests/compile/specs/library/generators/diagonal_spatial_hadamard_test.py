from functools import partial

import pytest
import stim

from tests.compile._distance import exact_circuit_distance
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import relabel_circuits_qubit_indices
from tqec.circuit.schedule.manipulation import merge_scheduled_circuits
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import fixed_bulk_convention
from tqec.compile.specs.library.generators.diagonal_spatial_hadamard import (
    SpatialHadamardFlagMode,
    make_diagonal_spatial_hadamard_extended_plaquettes,
    make_diagonal_spatial_hadamard_plaquette_pair,
)
from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.computation.block_graph import BlockGraph
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.plaquette import Plaquette
from tqec.utils.enums import Basis, Orientation
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def test_diagonal_stretched_stabilizer_gate_schedule() -> None:
    top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(Basis.Z)
    assert top.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
        RX 2
        TICK
        CX 2 3
        TICK
        CZ 2 1
        TICK
        CZ 2 0
        TICK
        TICK
        TICK
        CX 3 2
        TICK
        TICK
        M 2
    """)
    assert bottom.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
        R 2
        TICK
        TICK
        CX 3 2
        TICK
        CX 2 0
        TICK
        CX 2 1
        TICK
        TICK
        TICK
        CX 2 3
        TICK
        MX 2
    """)


@pytest.mark.parametrize("mode", tuple(SpatialHadamardFlagMode))
@pytest.mark.parametrize("initial,final", [(True, False), (False, False), (False, True)])
def test_flag_measurement_lifecycle(
    mode: SpatialHadamardFlagMode, initial: bool, final: bool
) -> None:
    top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(
        Basis.Z, Basis.Z if initial else None, Basis.Z if final else None, mode
    )
    auxiliary, shared = tuple(top.qubits.syndrome_qubits_indices)
    reset = top.circuit.moment_at_schedule(0).circuit
    readout = (
        top.circuit.moment_at_schedule(8).circuit if 8 in top.circuit.schedule else stim.Circuit()
    )
    reset_targets = {
        t.value
        for i in reset
        if isinstance(i, stim.CircuitInstruction) and i.name == "R"
        for t in i.targets_copy()
    }
    measurement_targets = {
        t.value
        for i in readout
        if isinstance(i, stim.CircuitInstruction) and i.name == "M"
        for t in i.targets_copy()
    }
    assert (shared in reset_targets) == (initial or mode != SpatialHadamardFlagMode.PARTIAL)
    assert (shared in measurement_targets) == (
        mode == SpatialHadamardFlagMode.ALL or (mode == SpatialHadamardFlagMode.PARTIAL and final)
    )
    assert (auxiliary in measurement_targets) == (mode != SpatialHadamardFlagMode.NONE)
    assert any(i.name == "MX" for i in bottom.circuit.moment_at_schedule(8).circuit)


def test_flag_metadata_survives_projection_compilation_and_serialization() -> None:
    top, _ = make_diagonal_spatial_hadamard_plaquette_pair(Basis.Z)
    projected = top.project_on_data_qubit_indices([1])
    compiled = IdentityPlaquetteCompiler.compile(projected)
    recovered = Plaquette.from_dict(compiled.to_dict())
    assert recovered.has_flagged_stabilizer
    assert recovered.circuit.get_circuit() == projected.circuit.get_circuit()


@pytest.mark.parametrize("orientation", tuple(Orientation))
def test_extended_plaquette_preview_follows_interface_orientation(orientation: Orientation) -> None:
    collection = make_diagonal_spatial_hadamard_extended_plaquettes(orientation=orientation)
    drawing = str(collection[Basis.Z].bulk.top.debug_information.get_svg_drawer().draw("interface"))
    assert ("matrix(0 1 1 0 0 0)" in drawing) == (orientation == Orientation.HORIZONTAL)
    assert "text" in drawing


@pytest.mark.parametrize("fault_half", [0, 1])
def test_partial_flags_detect_both_auxiliary_hook_faults(fault_half: int) -> None:
    rounds = []
    flag_offsets = []
    for initial in (True, False):
        top, bottom = make_diagonal_spatial_hadamard_plaquette_pair(
            Basis.Z, Basis.Z if initial else None
        )
        halves, qubit_map = relabel_circuits_qubit_indices(
            [
                top.circuit,
                bottom.circuit.map_to_qubits(lambda q: GridQubit(q.x, q.y + 2)),
            ]
        )
        round_circuit = merge_scheduled_circuits(
            halves, qubit_map, top.mergeable_instructions
        ).get_circuit()
        auxiliary = qubit_map.q2i[GridQubit(0, 2 * fault_half)]
        faulty_round = stim.Circuit()
        timestep = 0
        for instruction in round_circuit:
            faulty_round.append(instruction)
            if instruction.name == "TICK":
                timestep += 1
                if initial and timestep == (2 if fault_half == 0 else 3):
                    faulty_round.append("X_ERROR", [auxiliary], [1])
        rounds.append(faulty_round)
        flag_offsets.append(sum(c.num_measurements for c in rounds) - 2)
    circuit = rounds[0] + stim.Circuit("TICK") + rounds[1]
    for offset in flag_offsets:
        circuit.append("DETECTOR", [stim.target_rec(offset - circuit.num_measurements)])
    noiseless = stim.Circuit()
    for instruction in circuit:
        if instruction.name != "X_ERROR":
            noiseless.append(instruction)
    noiseless_detectors, _ = noiseless.compile_detector_sampler().sample(
        16, separate_observables=True
    )
    faulty_detectors, _ = circuit.compile_detector_sampler().sample(16, separate_observables=True)
    assert not noiseless_detectors.any()
    assert faulty_detectors.any(axis=1).all()


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    "k", [1, pytest.param(2, marks=pytest.mark.slow), pytest.param(3, marks=pytest.mark.slow)]
)
@pytest.mark.parametrize("orientation", tuple(Orientation))
@pytest.mark.parametrize("mode", tuple(SpatialHadamardFlagMode))
def test_diagonal_spatial_hadamard_sampling_and_distance(
    k: int, orientation: Orientation, mode: SpatialHadamardFlagMode
) -> None:
    horizontal = orientation == Orientation.HORIZONTAL
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "ZXZ" if horizontal else "XZZ")
    second = graph.add_cube(
        Position3D(int(horizontal), int(not horizontal), 0), "XZX" if horizontal else "ZXX"
    )
    graph.add_pipe(first, second)
    convention = fixed_bulk_convention(
        DIAGONAL_SCHEDULE_FAMILY,
        spatial_hadamard_factory=partial(
            make_diagonal_spatial_hadamard_extended_plaquettes, flag_mode=mode
        ),
    )
    for surface in graph.find_correlation_surfaces():
        circuit = (
            compile_block_graph(graph, convention, [surface])
            .to_layer_tree()
            .generate_circuit(k, database_path=None)
        )
        detectors, observables = circuit.compile_detector_sampler().sample(
            256, separate_observables=True
        )
        assert not detectors.any()
        assert not observables.any()
        assert circuit.num_observables == 1
        noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)
        assert noisy.detector_error_model(decompose_errors=False).num_observables == 1
        # Exact integer optimization at k=3 exceeds the test time budget.
        # Keep deterministic sampling and error-model validation at that size.
        if k <= 2:
            expected = k + 1 if mode == SpatialHadamardFlagMode.NONE else 2 * k + 1
            assert exact_circuit_distance(noisy) == expected


@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("endpoint", [0, 1])
@pytest.mark.parametrize("future", [False, True])
def test_diagonal_spatial_hadamard_preserves_temporal_endpoint(
    horizontal: bool, endpoint: int, future: bool
) -> None:
    graph = BlockGraph()
    positions = [Position3D(0, 0, 0), Position3D(int(horizontal), int(not horizontal), 0)]
    kinds = ["ZXZ", "XZX"] if horizontal else ["XZZ", "ZXX"]
    cubes = [graph.add_cube(position, kind) for position, kind in zip(positions, kinds)]
    graph.add_pipe(cubes[0], cubes[1])
    temporal_cube = graph.add_cube(
        positions[endpoint].shift_by(dz=1 if future else -1), kinds[endpoint]
    )
    graph.add_pipe(cubes[endpoint], temporal_cube)
    circuit = (
        compile_block_graph(graph, fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY))
        .to_layer_tree()
        .generate_circuit(1, database_path=None)
    )
    circuit.detector_error_model()
    detectors, observables = circuit.compile_detector_sampler().sample(
        256, separate_observables=True
    )
    assert not detectors.any()
    assert not observables.any()


def test_diagonal_spatial_hadamard_at_L_junction() -> None:
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "XXZ")
    junction = graph.add_cube(Position3D(0, 1, 0), "ZZX")
    last = graph.add_cube(Position3D(1, 1, 0), "ZZX")
    graph.add_pipe(first, junction)
    graph.add_pipe(junction, last)
    circuit = (
        compile_block_graph(graph, fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY))
        .to_layer_tree()
        .generate_circuit(1, database_path=None)
    )
    detectors, observables = circuit.compile_detector_sampler().sample(
        256, separate_observables=True
    )
    assert not detectors.any()
    assert not observables.any()
    assert (
        exact_circuit_distance(NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)) == 3
    )


@pytest.mark.parametrize("horizontal", [False, True])
def test_diagonal_spatial_hadamard_with_reversed_data_bases(horizontal: bool) -> None:
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "XZX" if horizontal else "ZXX")
    second = graph.add_cube(
        Position3D(int(horizontal), int(not horizontal), 0), "ZXZ" if horizontal else "XZZ"
    )
    graph.add_pipe(first, second)
    circuit = (
        compile_block_graph(graph, fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY))
        .to_layer_tree()
        .generate_circuit(1, database_path=None)
    )
    assert (
        exact_circuit_distance(NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)) == 3
    )
