import itertools
from pathlib import Path

import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import (
    FIXED_BULK_CONVENTION,
    FIXED_PARITY_CONVENTION,
    Convention,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.stability import stability
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Direction3D, Position3D


def generate_circuit_and_assert(
    g: BlockGraph,
    k: int,
    convention: Convention,
    expected_distance: int | None = None,
    expected_num_detectors: int | None = None,
    expected_num_observables: int | None = None,
    debug_output_dir: str | Path | None = None,
) -> None:
    if debug_output_dir is not None:
        debug_output_dir = Path(debug_output_dir)
        debug_output_dir.mkdir(parents=True, exist_ok=True)
        g.view_as_html(debug_output_dir / "block_graph.html")

    correlation_surfaces = g.find_correlation_surfaces()
    if debug_output_dir is not None and correlation_surfaces:
        surface_dir = debug_output_dir / "correlation_surfaces"
        surface_dir.mkdir(exist_ok=True)
        for i, surface in enumerate(correlation_surfaces):
            g.view_as_html(
                surface_dir / f"correlation_surface_{i}.html",
                show_correlation_surface=surface,
                pop_faces_at_direction="-Y",
            )

    compiled_graph = compile_block_graph(g, convention, correlation_surfaces)
    layer_tree = compiled_graph.to_layer_tree()
    if debug_output_dir is not None:
        svg_out_dir = debug_output_dir / "layers" / "raw"
        svg_out_dir.mkdir(parents=True, exist_ok=True)
        for i, svg_text in enumerate(layer_tree.layers_to_svg(k)):
            with open(svg_out_dir / f"{i}.svg", "w") as f:
                f.write(svg_text)

    circuit = layer_tree.generate_circuit(k)
    noise_model = NoiseModel.uniform_depolarizing(0.001)
    noisy_circuit = noise_model.noisy_circuit(circuit)
    # layers svg with observable annotations
    # need to be generated after the circuit is generated because we need to
    # annotate the observables in the layer tree
    if debug_output_dir is not None:
        for obs_idx in range(len(correlation_surfaces)):
            svg_out_dir = debug_output_dir / "layers" / f"with_observable{obs_idx}"
            svg_out_dir.mkdir(exist_ok=True)
            for i, svg_text in enumerate(layer_tree.layers_to_svg(k, show_observable=obs_idx)):
                with open(svg_out_dir / f"{i}.svg", "w") as f:
                    f.write(svg_text)

    logical_error = noisy_circuit.shortest_graphlike_error(
        ignore_ungraphlike_errors=False, canonicalize_circuit_errors=True
    )
    d = len(logical_error)

    if debug_output_dir is not None:
        circuit.to_file(debug_output_dir / "circuit_ideal.stim")
        noisy_circuit.to_file(debug_output_dir / "circuit_noisy.stim")
        noisy_circuit.detector_error_model(decompose_errors=True).to_file(
            debug_output_dir / "detector_error_model.dem"
        )
        with open(debug_output_dir / "crumble_url.txt", "w") as f:
            f.write(layer_tree.generate_crumble_url(k))
        svg_out_dir = debug_output_dir / "layers" / "with_logical_error"
        svg_out_dir.mkdir(exist_ok=True)
        for i, svg_text in enumerate(layer_tree.layers_to_svg(k, logical_error)):
            with open(svg_out_dir / f"{i}.svg", "w") as f:
                f.write(svg_text)

    if expected_distance is not None:
        assert d == expected_distance
    if expected_num_detectors is not None:
        assert circuit.num_detectors == expected_num_detectors
    if expected_num_observables is not None:
        assert circuit.num_observables == expected_num_observables


CONVENTIONS = (FIXED_BULK_CONVENTION, FIXED_PARITY_CONVENTION)


@pytest.mark.parametrize(
    ("convention", "kind", "k"),
    itertools.product(
        CONVENTIONS,
        ("ZXZ", "ZXX", "XZX", "XZZ"),
        (1,),
    ),
)
def test_compile_memory(convention: Convention, kind: str, k: int) -> None:
    g = BlockGraph("Memory Experiment")
    g.add_cube(Position3D(0, 0, 0), kind)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=(d**2 - 1) * d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "kind", "k", "xy"),
    itertools.product(
        CONVENTIONS,
        ("ZXZ", "ZXX", "XZX", "XZZ"),
        (1,),
        ((0, 0), (1, 1), (2, 2), (-1, -1)),
    ),
)
def test_compile_two_same_blocks_connected_in_time(
    convention: Convention, kind: str, k: int, xy: tuple[int, int]
) -> None:
    g = BlockGraph("Two Same Blocks in Time Experiment")
    p1 = Position3D(*xy, 0)
    p2 = Position3D(*xy, 1)
    g.add_cube(p1, kind)
    g.add_cube(p2, kind)
    g.add_pipe(p1, p2)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=(d**2 - 1) * 2 * d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "kinds", "k"),
    itertools.product(
        CONVENTIONS,
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
    convention: Convention, kinds: tuple[str, str], k: int
) -> None:
    g = BlockGraph("Two Same Blocks in Space Experiment")
    cube_kind, pipe_kind = kinds[0], kinds[1]
    p1 = Position3D(-1, 0, 0)
    shift = [0, 0, 0]
    shift[PipeKind.from_str(pipe_kind).direction.value] = 1
    p2 = p1.shift_by(*shift)
    g.add_cube(p1, cube_kind)
    g.add_cube(p2, cube_kind)
    g.add_pipe(p1, p2)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1),
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "kinds", "k"),
    itertools.product(
        CONVENTIONS,
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
    convention: Convention, kinds: tuple[str, str], k: int
) -> None:
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

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=2 * (d**2 - 1) + (d + 1 + 2 * (d**2 - 1)) * (d - 1) + (d**2 - 1) * d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        (Basis.X, Basis.Z),
        (1,),
    ),
)
def test_compile_logical_cnot(convention: Convention, obs_basis: Basis, k: int) -> None:
    g = cnot(obs_basis)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=2,
    )


@pytest.mark.parametrize(
    ("convention", "obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_stability(convention: Convention, obs_basis: Basis, k: int) -> None:
    g = stability(obs_basis)

    d = 2 * k + 1
    num_spatial_basis_stabilizers = (d - 1) // 2 * 4 + (d - 1) ** 2 // 2
    num_temporal_basis_stabilizers = (d - 1) ** 2 // 2
    num_detectors = (d - 1) * num_spatial_basis_stabilizers + (
        d + 1
    ) * num_temporal_basis_stabilizers
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=num_detectors,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "k"),
    itertools.product(CONVENTIONS, (1, 2)),
)
def test_compile_L_spatial_junction(convention: Convention, k: int) -> None:
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)

    d = 2 * k if convention.name == "fixed_parity" else 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_move_rotation(convention: Convention, obs_basis: Basis, k: int) -> None:
    g = move_rotation(obs_basis)

    d = 2 * k + 1
    if convention.name == "fixed_bulk":
        expected_distance = d
    else:
        expected_distance = d - 1 if obs_basis == Basis.X else d
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=expected_distance,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "k", "in_future"),
    itertools.product(CONVENTIONS, (1, 2), (False, True)),
)
def test_compile_L_spatial_junction_with_time_pipe(
    convention: Convention, k: int, in_future: bool
) -> None:
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    n4 = g.add_cube(Position3D(1, 1, 1 if in_future else -1), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    g.add_pipe(n3, n4)

    d = 2 * k if convention.name == "fixed_parity" else 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "in_obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_temporal_hadamard(convention: Convention, in_obs_basis: Basis, k: int) -> None:
    g = BlockGraph("Test Temporal Hadamard")
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ" if in_obs_basis == Basis.Z else "XZX")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXX" if in_obs_basis == Basis.Z else "ZXZ")
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "h_top_obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        [Basis.X, Basis.Z],
        (1, 2),
    ),
)
def test_compile_bell_state_with_single_temporal_hadamard(
    convention: Convention, h_top_obs_basis: Basis, k: int
) -> None:
    g = BlockGraph("Test Bell State with a Temporal Hadamard")
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ")
    n2 = g.add_cube(Position3D(0, 1, 0), "XZZ")
    n3 = g.add_cube(Position3D(0, 0, 1), "ZX" + h_top_obs_basis.value)
    n4 = g.add_cube(Position3D(0, 1, 1), "XZ" + h_top_obs_basis.flipped().value)
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    g.add_pipe(n2, n4)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
    )


@pytest.mark.parametrize(
    ("convention", "direction", "k"),
    itertools.product(
        CONVENTIONS,
        (Direction3D.X, Direction3D.Y),
        (1, 2),
    ),
)
def test_compile_spatial_hadamard_vertical_correlation_surface(
    convention: Convention, direction: Direction3D, k: int
) -> None:
    g = BlockGraph("Test Temporal Hadamard with Vertical Correlation Surface")
    kind_before_hadamard = "ZXZ" if direction == Direction3D.X else "XZZ"
    n1 = g.add_cube(Position3D(0, 0, 0), kind_before_hadamard)
    kind_after_hadamard = "XZX" if direction == Direction3D.X else "ZXX"
    n2 = g.add_cube(Position3D(0, 0, 0).shift_in_direction(direction, 1), kind_after_hadamard)
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    if convention.name == "fixed_bulk":
        with pytest.raises(NotImplementedError):
            generate_circuit_and_assert(
                g,
                k,
                convention,
                expected_distance=d,
                expected_num_observables=1,
            )
    else:
        generate_circuit_and_assert(
            g,
            k,
            convention,
            expected_distance=d,
            expected_num_observables=1,
        )


@pytest.mark.skip(reason="Hadamard around spatial junction is not implemented yet.")
@pytest.mark.parametrize(
    ("convention", "direction", "obs_basis", "k"),
    itertools.product(
        CONVENTIONS,
        (Direction3D.X, Direction3D.Y),
        (Basis.X, Basis.Z),
        (1, 2),
    ),
)
def test_compile_spatial_hadamard_horizontal_correlation_surface(
    convention: Convention, direction: Direction3D, obs_basis: Basis, k: int
) -> None:
    g = BlockGraph("Test Temporal Hadamard with Horizontal Correlation Surface")
    kind_before_hadamard = "ZZX" if obs_basis == Basis.Z else "XXZ"
    n1 = g.add_cube(Position3D(0, 0, 0), kind_before_hadamard)
    kind_after_hadamard = "XXZ" if obs_basis == Basis.Z else "ZZX"
    n2 = g.add_cube(Position3D(0, 0, 0).shift_in_direction(direction, 1), kind_after_hadamard)
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    if convention.name == "fixed_bulk":
        with pytest.raises(NotImplementedError):
            generate_circuit_and_assert(
                g,
                k,
                convention,
                expected_distance=d,
                expected_num_observables=1,
            )
    else:
        generate_circuit_and_assert(
            g,
            k,
            convention,
            expected_distance=d,
            expected_num_observables=1,
            debug_output_dir="debug",
        )


@pytest.mark.parametrize(
    ("convention", "shape", "basis", "k"),
    # itertools.product(
    #     CONVENTIONS,
    #     ("⊣", "T", "⊥", "⊢"),
    #     (Basis.X, Basis.Z),
    #     (1,),
    # ),
    itertools.product(
        (FIXED_PARITY_CONVENTION,),
        ("⊢",),
        (Basis.Z,),
        (1,),
    ),
)
def test_compile_three_way_shape_spatial_junction(
    convention: Convention, shape: str, basis: Basis, k: int
) -> None:
    g = BlockGraph(f"{shape}-shape Spatial Junction")
    cube_kind = "ZZX" if basis == Basis.Z else "XXZ"
    n0 = g.add_cube(Position3D(0, 0, 0), cube_kind)
    if shape == "⊣":
        n1 = g.add_cube(Position3D(0, 1, 0), cube_kind)
        n2 = g.add_cube(Position3D(0, -1, 0), cube_kind)
        n3 = g.add_cube(Position3D(-1, 0, 0), cube_kind)
    elif shape == "T":
        n1 = g.add_cube(Position3D(0, 1, 0), cube_kind)
        n2 = g.add_cube(Position3D(-1, 0, 0), cube_kind)
        n3 = g.add_cube(Position3D(1, 0, 0), cube_kind)
    elif shape == "⊥":
        n1 = g.add_cube(Position3D(0, -1, 0), cube_kind)
        n2 = g.add_cube(Position3D(-1, 0, 0), cube_kind)
        n3 = g.add_cube(Position3D(1, 0, 0), cube_kind)
    else:  # shape == "⊢":
        n1 = g.add_cube(Position3D(0, 1, 0), cube_kind)
        n2 = g.add_cube(Position3D(0, -1, 0), cube_kind)
        n3 = g.add_cube(Position3D(1, 0, 0), cube_kind)
    g.add_pipe(n0, n1)
    g.add_pipe(n0, n2)
    g.add_pipe(n0, n3)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
        debug_output_dir="debug",
    )
