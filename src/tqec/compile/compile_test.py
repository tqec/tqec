import itertools
from typing import Literal

import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder
from tqec.compile.specs.library.css import CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER
from tqec.compile.specs.library.zxxz import (
    ZXXZ_BLOCK_BUILDER,
    ZXXZ_SUBSTITUTION_BUILDER,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.logical_cnot import logical_cnot_block_graph
from tqec.noise_model import NoiseModel
from tqec.position import Position3D

SPECS: dict[str, tuple[BlockBuilder, SubstitutionBuilder]] = {
    "CSS": (CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER),
    "ZXXZ": (ZXXZ_BLOCK_BUILDER, ZXXZ_SUBSTITUTION_BUILDER),
}


@pytest.mark.parametrize(
    ("spec", "kind", "k"),
    itertools.product(SPECS.keys(), ("ZXZ", "ZXX", "XZX", "XZZ"), (1,)),
)
def test_compile_single_block_memory(spec: str, kind: str, k: int) -> None:
    d = 2 * k + 1
    g = BlockGraph("Single Block Memory Experiment")
    g.add_node(Cube(Position3D(0, 0, 0), ZXCube.from_str(kind)))
    block_builder, substitution_builder = SPECS[spec]
    observables, _ = g.get_abstract_observables()
    assert len(observables) == 1
    compiled_graph = compile_block_graph(
        g, block_builder, substitution_builder, observables
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    assert circuit.num_detectors == (d**2 - 1) * d
    assert len(circuit.shortest_graphlike_error()) == d


@pytest.mark.parametrize(
    ("spec", "kind", "k"),
    itertools.product(SPECS.keys(), ("ZXZ", "ZXX", "XZX", "XZZ"), (1,)),
)
def test_compile_two_same_blocks_connected_in_time(
    spec: str, kind: str, k: int
) -> None:
    d = 2 * k + 1
    g = BlockGraph("Two Same Blocks in Time Experiment")
    p1 = Position3D(1, 1, 0)
    p2 = Position3D(1, 1, 1)
    cube1 = Cube(p1, ZXCube.from_str(kind))
    cube2 = Cube(p2, ZXCube.from_str(kind))
    pipe_kind = PipeKind.from_str(kind[:2] + "O")
    g.add_edge(cube1, cube2, pipe_kind)

    block_builder, substitution_builder = SPECS[spec]
    observables, _ = g.get_abstract_observables()
    assert len(observables) == 1
    compiled_graph = compile_block_graph(
        g, block_builder, substitution_builder, observables
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_detectors == (d**2 - 1) * 2 * d
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d


@pytest.mark.parametrize(
    ("spec", "kinds", "k"),
    itertools.product(
        SPECS.keys(),
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
    cube_kind, pipe_kind = ZXCube.from_str(kinds[0]), PipeKind.from_str(kinds[1])
    p1 = Position3D(-1, 0, 0)
    shift = [0, 0, 0]
    shift[pipe_kind.direction.value] = 1
    p2 = p1.shift_by(*shift)
    cube1 = Cube(p1, cube_kind)
    cube2 = Cube(p2, cube_kind)
    g.add_edge(cube1, cube2, pipe_kind)

    block_builder, substitution_builder = SPECS[spec]
    observables, _ = g.get_abstract_observables()
    assert len(observables) == 1
    compiled_graph = compile_block_graph(
        g, block_builder, substitution_builder, observables
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_detectors == 2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1)
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d


@pytest.mark.parametrize(
    ("spec", "kinds", "k"),
    itertools.product(
        SPECS.keys(),
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
    spec: str, kinds: tuple[str, str], k: int
) -> None:
    d = 2 * k + 1
    g = BlockGraph("L-shape Blocks Experiment")
    cube_kind, space_pipe_kind = ZXCube.from_str(kinds[0]), PipeKind.from_str(kinds[1])
    time_pipe_type = PipeKind.from_str(kinds[0][:2] + "O")
    p1 = Position3D(1, 2, 0)
    space_shift = [0, 0, 0]
    space_shift[space_pipe_kind.direction.value] = 1
    p2 = p1.shift_by(*space_shift)
    p3 = p2.shift_by(dz=1)
    cube1 = Cube(p1, cube_kind)
    cube2 = Cube(p2, cube_kind)
    cube3 = Cube(p3, cube_kind)
    g.add_edge(cube1, cube2, space_pipe_kind)
    g.add_edge(cube2, cube3, time_pipe_type)

    block_builder, substitution_builder = SPECS[spec]
    observables, _ = g.get_abstract_observables()
    assert len(observables) == 1
    compiled_graph = compile_block_graph(
        g, block_builder, substitution_builder, observables
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert (
        dem.num_detectors
        == 2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1) + (d**2 - 1) * d
    )
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d


@pytest.mark.parametrize(
    ("spec", "support_observable_basis", "k"),
    itertools.product(
        SPECS.keys(),
        ("X", "Z"),
        (1,),
    ),
)
def test_compile_logical_cnot(
    spec: str, support_observable_basis: Literal["Z", "X"], k: int
) -> None:
    d = 2 * k + 1
    g = logical_cnot_block_graph(support_observable_basis)

    block_builder, substitution_builder = SPECS[spec]
    observables, _ = g.get_abstract_observables()
    assert len(observables) == 3
    compiled_graph = compile_block_graph(
        g, block_builder, substitution_builder, observables
    )
    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_observables == 3
    assert len(dem.shortest_graphlike_error()) == d
