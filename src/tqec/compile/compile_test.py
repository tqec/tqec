import itertools

import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.specs.library import ALL_SPECS
from tqec.computation.block_graph import BlockGraph
from tqec.computation.pipe import PipeKind
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


@pytest.mark.parametrize(
    ("spec", "kind", "k"),
    itertools.product(ALL_SPECS.keys(), ("ZXZ", "ZXX", "XZX", "XZZ"), (1,)),
)
def test_compile_single_block_memory(spec: str, kind: str, k: int) -> None:
    d = 2 * k + 1
    g = BlockGraph("Single Block Memory Experiment")
    g.add_cube(Position3D(0, 0, 0), kind)
    cube_builder, pipe_builder = ALL_SPECS[spec]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(
        g, cube_builder, pipe_builder, correlation_surfaces
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    assert circuit.num_detectors == (d**2 - 1) * d
    assert len(circuit.shortest_graphlike_error()) == d


@pytest.mark.parametrize(
    ("spec", "kind", "k", "xy"),
    itertools.product(
        ALL_SPECS.keys(),
        ("ZXZ", "ZXX", "XZX", "XZZ"),
        (1,),
        ((0, 0), (1, 1), (2, 2)),
    ),
)
def test_compile_two_same_blocks_connected_in_time(
    spec: str, kind: str, k: int, xy: tuple[int, int]
) -> None:
    d = 2 * k + 1
    g = BlockGraph("Two Same Blocks in Time Experiment")
    p1 = Position3D(*xy, 0)
    p2 = Position3D(*xy, 1)
    g.add_cube(p1, kind)
    g.add_cube(p2, kind)
    g.add_pipe(p1, p2)

    cube_builder, pipe_builder = ALL_SPECS[spec]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(
        g, cube_builder, pipe_builder, correlation_surfaces
    )

    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_detectors == (d**2 - 1) * 2 * d
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d


# FIXME: test failed
@pytest.mark.parametrize(
    ("spec", "kinds", "k"),
    itertools.product(
        ALL_SPECS.keys(),
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
    spec: str, kinds: tuple[str, str], k: int
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

    cube_builder, pipe_builder = ALL_SPECS[spec]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph(
        g, cube_builder, pipe_builder, correlation_surfaces
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_detectors == 2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d
