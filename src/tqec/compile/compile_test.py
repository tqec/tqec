import itertools

import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import ALL_CONVENTIONS
from tqec.computation.block_graph import BlockGraph
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.cz import cz
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.stability import stability
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


@pytest.mark.parametrize(
    ("convention_name", "kind", "k"),
    itertools.product(ALL_CONVENTIONS.keys(), ("ZXZ", "ZXX", "XZX", "XZZ"), (1,)),
)
def test_compile_single_block_memory(convention_name: str, kind: str, k: int) -> None:
    d = 2 * k + 1
    g = BlockGraph("Single Block Memory Experiment")
    g.add_cube(Position3D(0, 0, 0), kind)
    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_detectors == (d**2 - 1) * d
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "kind", "k", "xy"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        ("ZXZ", "ZXX", "XZX", "XZZ"),
        (1,),
        ((0, 0), (1, 1), (2, 2), (-1, -1)),
    ),
)
def test_compile_two_same_blocks_connected_in_time(
    convention_name: str, kind: str, k: int, xy: tuple[int, int]
) -> None:
    d = 2 * k + 1
    g = BlockGraph("Two Same Blocks in Time Experiment")
    p1 = Position3D(*xy, 0)
    p2 = Position3D(*xy, 1)
    g.add_cube(p1, kind)
    g.add_cube(p2, kind)
    g.add_pipe(p1, p2)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)

    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_detectors == (d**2 - 1) * 2 * d
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "kinds", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (
            ("ZXZ", "OXZ"),
            ("ZXX", "ZOX"),
            ("XZX", "OZX"),
            ("XZZ", "XOZ"),
        ),
        (1,),
    ),
)
def test_compile_two_same_blocks_connected_in_space(
    convention_name: str, kinds: tuple[str, str], k: int
) -> None:
    d = 2 * k + 1
    g = BlockGraph("Two Same Blocks in Space Experiment")
    cube_kind, pipe_kind = kinds[0], kinds[1]
    p1 = Position3D(-1, 0, 0)
    shift = [0, 0, 0]
    shift[PipeKind.from_str(pipe_kind).direction.value] = 1
    p2 = p1.shift_by(*shift)
    g.add_cube(p1, cube_kind)
    g.add_cube(p2, cube_kind)
    g.add_pipe(p1, p2)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_detectors == 2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "kinds", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (
            ("ZXZ", "OXZ"),
            ("ZXX", "ZOX"),
            ("XZX", "OZX"),
            ("XZZ", "XOZ"),
        ),
        (1,),
    ),
)
def test_compile_L_shape_in_space_time(
    convention_name: str, kinds: tuple[str, str], k: int
) -> None:
    d = 2 * k + 1
    g = BlockGraph("L-shape Blocks Experiment")
    cube_kind, space_pipe_kind = kinds[0], kinds[1]
    time_pipe_type = PipeKind.from_str(kinds[0][:2] + "O")
    p1 = Position3D(1, 2, 0)
    space_shift = [0, 0, 0]
    space_shift[PipeKind.from_str(space_pipe_kind).direction.value] = 1
    p2 = p1.shift_by(*space_shift)
    p3 = p2.shift_by(dz=1)
    g.add_cube(p1, cube_kind)
    g.add_cube(p2, cube_kind)
    g.add_cube(p3, cube_kind)
    g.add_pipe(p1, p2, space_pipe_kind)
    g.add_pipe(p2, p3, time_pipe_type)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_detectors == 2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1) + (d**2 - 1) * d
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "obs_basis", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (Basis.X, Basis.Z),
        (1,),
    ),
)
def test_compile_logical_cnot(convention_name: str, obs_basis: Basis, k: int) -> None:
    d = 2 * k + 1
    g = cnot(obs_basis)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 2
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 2
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "obs_basis", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_stability(convention_name: str, obs_basis: Basis, k: int) -> None:
    d = 2 * k + 1
    g = stability(obs_basis)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    num_spatial_basis_stabilizers = (d - 1) // 2 * 4 + (d - 1) ** 2 // 2
    num_temporal_basis_stabilizers = (d - 1) ** 2 // 2
    assert (
        dem.num_detectors
        == (d - 1) * num_spatial_basis_stabilizers + (d + 1) * num_temporal_basis_stabilizers
    )
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "k"),
    itertools.product(ALL_CONVENTIONS.keys(), (1, 2)),
)
def test_compile_L_spatial_junction(convention_name: str, k: int) -> None:
    d = 2 * k + 1
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    expected_distance = d - 1 if convention_name == "fixed_parity" else d
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == expected_distance


@pytest.mark.parametrize(
    ("convention_name", "obs_basis", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_move_rotation(convention_name: str, obs_basis: Basis, k: int) -> None:
    d = 2 * k + 1
    g = move_rotation(obs_basis)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    if convention_name == "fixed_bulk":
        expected_distance = d
    else:
        expected_distance = d - 1 if obs_basis == Basis.X else d
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == expected_distance


@pytest.mark.parametrize(
    ("convention_name", "k", "in_future"),
    itertools.product(ALL_CONVENTIONS.keys(), (1, 2), (False, True)),
)
def test_compile_L_spatial_junction_with_time_pipe(
    convention_name: str, k: int, in_future: bool
) -> None:
    d = 2 * k + 1
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    n4 = g.add_cube(Position3D(1, 1, 1 if in_future else -1), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    g.add_pipe(n3, n4)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    expected_distance = d - 1 if convention_name == "fixed_parity" else d
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == expected_distance


@pytest.mark.parametrize(
    ("convention_name", "in_obs_basis", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_temporal_hadamard(convention_name: str, in_obs_basis: Basis, k: int) -> None:
    d = 2 * k + 1

    g = BlockGraph("Test Temporal Hadamard")
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ" if in_obs_basis == Basis.Z else "XZX")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXX" if in_obs_basis == Basis.Z else "ZXZ")
    g.add_pipe(n1, n2)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "h_top_obs_basis", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        [Basis.X, Basis.Z],
        (1, 2),
    ),
)
def test_compile_bell_state_with_single_temporal_hadamard(
    convention_name: str, h_top_obs_basis: Basis, k: int
) -> None:
    d = 2 * k + 1

    g = BlockGraph("Test Bell State with a Temporal Hadamard")
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ")
    n2 = g.add_cube(Position3D(0, 1, 0), "XZZ")
    n3 = g.add_cube(Position3D(0, 0, 1), "ZX" + h_top_obs_basis.value)
    n4 = g.add_cube(Position3D(0, 1, 1), "XZ" + h_top_obs_basis.flipped().value)
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    g.add_pipe(n2, n4)

    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d


@pytest.mark.parametrize(
    ("convention_name", "support_flows", "k"),
    itertools.product(
        ALL_CONVENTIONS.keys(),
        ("X_ -> XZ",),
        (1, 2),
    ),
)
def test_compile_cz(convention_name: str, support_flows: str | list[str], k: int) -> None:
    d = 2 * k + 1

    g = cz(support_flows)
    convention = ALL_CONVENTIONS[convention_name]
    correlation_surfaces = g.find_correlation_surfaces()
    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )
    dem = circuit.detector_error_model(decompose_errors=True)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error(ignore_ungraphlike_errors=False)) == d
