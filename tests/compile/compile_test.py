"""Notes on some of the tests cases.

Because circuit generation and checking that the circuit is correct are quite long operations (~4s
for most of the tests) and because the runtime scales with the scaling factor ``k``, only ``k == 1``
tests are done on a regular basis, and ``k == 2`` tests are only done when we can afford a longer
CI run (e.g., when pushing on the main branch).

Warning:
    Tests involving a spatial junction in the fixed boundary convention will fail for ``k >= 3``!
    That is explained in the documentation:
    https://tqec.github.io/tqec/user_guide/extended_stabilizers_implementation.html.

"""

import itertools
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pytest
import stim
from typing_extensions import TypeVarTuple, Unpack

from tqec.compile.compile import _DEFAULT_BLOCK_REPETITIONS, compile_block_graph
from tqec.compile.convention import (
    FIXED_BOUNDARY_CONVENTION,
    FIXED_BULK_CONVENTION,
    Convention,
)
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.detector import remove_non_deterministic_detectors
from tqec.computation.block_graph import BlockGraph
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.stability import stability
from tqec.gallery.steane_encoding import steane_encoding
from tqec.gallery.three_cnots import three_cnots
from tqec.utils.enums import Basis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.paths import _get_database_path
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.scale import LinearFunction

Ts = TypeVarTuple("Ts")


def generate_inputs(
    *args: Unpack[Ts],
    small_ks: Sequence[int] = (1,),
    larger_ks: Sequence[int] = (2,),
) -> Iterable[tuple[int, Unpack[Ts]] | Any]:
    # Currently not possible to return the correct type with typing. See
    # https://github.com/python/typing/issues/1216 for example.
    yield from itertools.product(small_ks, *args)
    yield from (
        pytest.param(k, *remaining, marks=pytest.mark.slow)
        for k, *remaining in itertools.product(larger_ks, *args)
    )


def generate_circuit_and_assert(
    g: BlockGraph,
    k: int,
    convention: Convention,
    expected_distance: int | None = None,
    expected_num_detectors: int | None = None,
    expected_num_observables: int | None = None,
    debug_output_dir: str | Path | None = None,
    block_temporal_height: LinearFunction = _DEFAULT_BLOCK_REPETITIONS,
    detector_db: DetectorDatabase | None = None,
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
                pop_faces_at_directions=("-Y",),
            )

    compiled_graph = compile_block_graph(g, convention, correlation_surfaces, block_temporal_height)
    layer_tree = compiled_graph.to_layer_tree()
    if debug_output_dir is not None:
        svg_out_dir = debug_output_dir / "layers" / "raw"
        svg_out_dir.mkdir(parents=True, exist_ok=True)
        for i, svg_text in enumerate(layer_tree.layers_to_svg(k)):
            with open(svg_out_dir / f"{i}.svg", "w") as f:
                f.write(svg_text)

    # Compile using the existing detector database, but to speed up testing,
    # don't pass in a path to write to each time the detector annotations
    # are updated.
    circuit = layer_tree.generate_circuit(k, detector_database=detector_db, database_path=None)
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


CONVENTIONS = (FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION)


@pytest.fixture(scope="session", name="filepath")
def fixture_filepath():
    return _get_database_path()


@pytest.fixture(scope="session", autouse=True)
def detector_db(filepath: Path):
    if filepath.exists():
        return DetectorDatabase.from_file(filepath)
    else:
        return DetectorDatabase()


@pytest.fixture(scope="session", autouse=True)
def save_to_db(filepath: Path, detector_db: DetectorDatabase):
    yield
    detector_db.to_file(filepath)


@pytest.mark.parametrize(
    ("k", "convention", "kind"),
    tuple(generate_inputs(CONVENTIONS, ("ZXZ", "ZXX", "XZX", "XZZ"))),
)
def test_compile_memory(
    convention: Convention, kind: str, k: int, detector_db: DetectorDatabase
) -> None:
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
        detector_db=detector_db,
    )


@pytest.mark.parametrize(
    ("k", "convention", "kind", "xy"),
    tuple(
        generate_inputs(
            CONVENTIONS, ("ZXZ", "ZXX", "XZX", "XZZ"), ((0, 0), (1, 1), (2, 2), (-1, -1))
        )
    ),
)
def test_compile_two_same_blocks_connected_in_time(
    convention: Convention, kind: str, k: int, xy: tuple[int, int], detector_db: DetectorDatabase
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
        detector_db=detector_db,
    )


@pytest.mark.parametrize(
    ("k", "convention", "kinds"),
    tuple(
        generate_inputs(
            CONVENTIONS, (("ZXZ", "OXZ"), ("ZXX", "ZOX"), ("XZX", "OZX"), ("XZZ", "XOZ"))
        )
    ),
)
def test_compile_two_same_blocks_connected_in_space(
    convention: Convention, kinds: tuple[str, str], k: int, detector_db: DetectorDatabase
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
        detector_db=detector_db,
    )


@pytest.mark.parametrize(
    ("k", "convention", "kinds"),
    tuple(
        generate_inputs(
            CONVENTIONS, (("ZXZ", "OXZ"), ("ZXX", "ZOX"), ("XZX", "OZX"), ("XZZ", "XOZ"))
        )
    ),
)
def test_compile_L_shape_in_space_time(
    convention: Convention, kinds: tuple[str, str], k: int, detector_db: DetectorDatabase
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
        detector_db=detector_db,
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "obs_basis"), tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z)))
)
def test_compile_logical_cnot(
    convention: Convention, obs_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = cnot(obs_basis)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=2, detector_db=detector_db
    )


@pytest.mark.parametrize(
    ("k", "convention", "obs_basis"), tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z)))
)
def test_compile_stability(
    convention: Convention, obs_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
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
        detector_db=detector_db,
    )


@pytest.mark.parametrize(("k", "convention"), tuple(generate_inputs(CONVENTIONS)))
def test_compile_L_spatial_junction(
    convention: Convention, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)

    d = 2 * k if convention.name == "fixed_boundary" else 2 * k + 1
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


@pytest.mark.parametrize(
    ("k", "convention", "obs_basis"), tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z)))
)
def test_compile_move_rotation(
    convention: Convention, obs_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
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
        detector_db=detector_db,
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "in_future"), tuple(generate_inputs(CONVENTIONS, (False, True)))
)
def test_compile_L_spatial_junction_with_time_pipe(
    convention: Convention, k: int, in_future: bool, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    n4 = g.add_cube(Position3D(1, 1, 1 if in_future else -1), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    g.add_pipe(n3, n4)

    d = 2 * k if convention.name == "fixed_boundary" else 2 * k + 1
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


@pytest.mark.parametrize(
    ("k", "convention", "in_obs_basis"),
    tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z))),
)
def test_compile_temporal_hadamard(
    convention: Convention, in_obs_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph("Test Temporal Hadamard")
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ" if in_obs_basis == Basis.Z else "XZX")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXX" if in_obs_basis == Basis.Z else "ZXZ")
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


@pytest.mark.parametrize(
    ("k", "convention", "h_top_obs_basis"),
    tuple(generate_inputs(CONVENTIONS, [Basis.X, Basis.Z])),
)
def test_compile_bell_state_with_single_temporal_hadamard(
    convention: Convention, h_top_obs_basis: Basis, k: int, detector_db: DetectorDatabase
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
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


def test_compile_observable_with_unrelated_temporal_hadamard() -> None:
    """An unrelated temporal Hadamard must not affect an observable."""
    graph = BlockGraph("Observable with unrelated temporal Hadamard")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_cube(Position3D(0, 0, 1), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    graph.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))

    (observable,) = graph.find_correlation_surfaces()

    # Add a disconnected temporal Hadamard on the same z slice.
    graph.add_cube(Position3D(3, 0, 0), "ZXZ")
    graph.add_cube(Position3D(3, 0, 1), "XZX")
    graph.add_pipe(Position3D(3, 0, 0), Position3D(3, 0, 1))

    circuit = compile_block_graph(
        graph,
        observables=[observable],
    ).generate_stim_circuit(k=1)

    _, observables = circuit.compile_detector_sampler().sample(
        4096,
        separate_observables=True,
    )

    observable_include_count = sum(
        len(instruction.targets_copy())
        for instruction in circuit.flattened()
        if isinstance(instruction, stim.CircuitInstruction)
        and instruction.name == "OBSERVABLE_INCLUDE"
    )

    assert not observables.any()
    # Before #1063 was fixed, the 4 top-readout records were dropped.
    assert observable_include_count == 7


@pytest.mark.parametrize(
    ("k", "convention", "direction"),
    tuple(generate_inputs(CONVENTIONS, (Direction3D.X, Direction3D.Y))),
)
def test_compile_spatial_hadamard_vertical_correlation_surface(
    convention: Convention, direction: Direction3D, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph("Test Spatial Hadamard with Vertical Correlation Surface")
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
                detector_db=detector_db,
            )
    else:
        generate_circuit_and_assert(
            g,
            k,
            convention,
            expected_distance=d,
            expected_num_observables=1,
            detector_db=detector_db,
        )


@pytest.mark.parametrize(
    ("k", "convention", "direction", "obs_basis"),
    tuple(generate_inputs(CONVENTIONS, (Direction3D.X, Direction3D.Y), (Basis.X, Basis.Z))),
)
def test_compile_spatial_hadamard_horizontal_correlation_surface(
    convention: Convention,
    direction: Direction3D,
    obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
) -> None:
    g = BlockGraph("Test Spatial Hadamard with Horizontal Correlation Surface")
    kind_before_hadamard = "ZZX" if obs_basis == Basis.Z else "XXZ"
    n1 = g.add_cube(Position3D(0, 0, 0), kind_before_hadamard)
    kind_after_hadamard = "XXZ" if obs_basis == Basis.Z else "ZZX"
    n2 = g.add_cube(Position3D(0, 0, 0).shift_in_direction(direction, 1), kind_after_hadamard)
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    if convention.name == "fixed_boundary":
        with pytest.raises(NotImplementedError):
            generate_circuit_and_assert(
                g,
                k,
                convention,
                expected_distance=d,
                expected_num_observables=1,
                detector_db=detector_db,
            )
    elif direction == Direction3D.X:
        with pytest.raises(NotImplementedError):
            generate_circuit_and_assert(
                g,
                k,
                convention,
                expected_distance=d,
                expected_num_observables=1,
                detector_db=detector_db,
            )
    else:
        generate_circuit_and_assert(
            g,
            k,
            convention,
            expected_distance=d,
            expected_num_observables=1,
            detector_db=detector_db,
        )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "shape", "basis"),
    tuple(generate_inputs(CONVENTIONS, ("⊣", "T", "⊥", "⊢"), (Basis.X, Basis.Z))),
)
def test_compile_three_way_junction_with_spatial_cube_endpoints(
    convention: Convention, shape: str, basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph(f"{shape}-shape Spatial Junction with Horizontal Correlation Surface")
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
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "shape", "spatial_basis"),
    tuple(generate_inputs(CONVENTIONS, ("⊣", "T", "⊥", "⊢"), (Basis.X, Basis.Z))),
)
def test_compile_three_way_junction_with_regular_cube_endpoints(
    convention: Convention, shape: str, spatial_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph(f"{shape}-shape Spatial Junction with Vertical Correlation Surface")

    def may_flip(z_basis_kind: str) -> str:
        if spatial_basis == Basis.X:
            return "".join("X" if b == "Z" else "Z" for b in z_basis_kind)
        return z_basis_kind

    center_cube_kind = may_flip("ZZX")
    n0 = g.add_cube(Position3D(0, 0, 0), center_cube_kind)

    kv, kh = may_flip("ZXX"), may_flip("XZX")

    if shape == "⊣":
        n1 = g.add_cube(Position3D(0, 1, 0), kv)
        n2 = g.add_cube(Position3D(0, -1, 0), kv)
        n3 = g.add_cube(Position3D(-1, 0, 0), kh)
    elif shape == "T":
        n1 = g.add_cube(Position3D(0, 1, 0), kv)
        n2 = g.add_cube(Position3D(-1, 0, 0), kh)
        n3 = g.add_cube(Position3D(1, 0, 0), kh)
    elif shape == "⊥":
        n1 = g.add_cube(Position3D(0, -1, 0), kv)
        n2 = g.add_cube(Position3D(-1, 0, 0), kh)
        n3 = g.add_cube(Position3D(1, 0, 0), kh)
    else:  # shape == "⊢":
        n1 = g.add_cube(Position3D(0, 1, 0), kv)
        n2 = g.add_cube(Position3D(0, -1, 0), kv)
        n3 = g.add_cube(Position3D(1, 0, 0), kh)
    g.add_pipe(n0, n1)
    g.add_pipe(n0, n2)
    g.add_pipe(n0, n3)

    d = 2 * k + 1 if convention.name == "fixed_bulk" else 2 * k
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=2,
        detector_db=detector_db,
    )


@pytest.mark.parametrize(
    ("k", "convention", "kind", "direction"),
    tuple(generate_inputs(CONVENTIONS, ("ZZX", "XXZ"), (Direction3D.X, Direction3D.Y))),
)
def test_compile_I_shape_stability_experiment_composed_of_three_cubes(
    convention: Convention, kind: str, direction: Direction3D, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph(f"Stability Experiment with Two {kind} Cubes in {direction.name} Direction")

    n0 = g.add_cube(Position3D(0, 0, 0), kind)
    n1 = g.add_cube(Position3D(0, 0, 0).shift_in_direction(direction, 1), kind)
    n2 = g.add_cube(Position3D(0, 0, 0).shift_in_direction(direction, 2), kind)
    g.add_pipe(n0, n1)
    g.add_pipe(n1, n2)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=1, detector_db=detector_db
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "kind", "shape"),
    tuple(generate_inputs(CONVENTIONS, ("ZZX", "XXZ"), ("H", "工"))),
)
def test_compile_H_shape_stability_experiment(
    convention: Convention, kind: str, shape: str, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph(f"Stability Experiment with {shape}-shape {kind} Cubes")

    if shape == "H":
        nodes = [
            g.add_cube(pos, kind)
            for pos in [
                Position3D(0, 0, 0),
                Position3D(0, 1, 0),
                Position3D(0, -1, 0),
                Position3D(1, 0, 0),
                Position3D(1, -1, 0),
                Position3D(1, 1, 0),
            ]
        ]
    else:
        nodes = [
            g.add_cube(pos, kind)
            for pos in [
                Position3D(0, 0, 0),
                Position3D(-1, 0, 0),
                Position3D(1, 0, 0),
                Position3D(0, 1, 0),
                Position3D(-1, 1, 0),
                Position3D(1, 1, 0),
            ]
        ]
    for edge in [(0, 1), (0, 2), (0, 3), (3, 4), (3, 5)]:
        g.add_pipe(nodes[edge[0]], nodes[edge[1]])

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=1,
        debug_output_dir="debug",
        detector_db=detector_db,
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "shape", "spatial_basis"),
    tuple(generate_inputs(CONVENTIONS, ("H", "工"), (Basis.X, Basis.Z))),
)
def test_compile_H_shape_junctions_with_regular_cube_endpoints(
    convention: Convention, shape: str, spatial_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = BlockGraph(f"{shape}-shape Junction with Regular Cube Endpoints")

    def may_flip(z_basis_kind: str) -> str:
        if spatial_basis == Basis.X:
            return "".join("X" if b == "Z" else "Z" for b in z_basis_kind)
        return z_basis_kind

    spatial_cube_kind = may_flip("ZZX")
    endpoint_cube_kind = may_flip("ZXX") if shape == "H" else may_flip("XZX")

    if shape == "H":
        nodes = [
            g.add_cube(pos, kind)
            for pos, kind in [
                (Position3D(0, 0, 0), spatial_cube_kind),
                (Position3D(0, 1, 0), endpoint_cube_kind),
                (Position3D(0, -1, 0), endpoint_cube_kind),
                (Position3D(1, 0, 0), spatial_cube_kind),
                (Position3D(1, -1, 0), endpoint_cube_kind),
                (Position3D(1, 1, 0), endpoint_cube_kind),
            ]
        ]
    else:
        nodes = [
            g.add_cube(pos, kind)
            for pos, kind in [
                (Position3D(0, 0, 0), spatial_cube_kind),
                (Position3D(-1, 0, 0), endpoint_cube_kind),
                (Position3D(1, 0, 0), endpoint_cube_kind),
                (Position3D(0, 1, 0), spatial_cube_kind),
                (Position3D(-1, 1, 0), endpoint_cube_kind),
                (Position3D(1, 1, 0), endpoint_cube_kind),
            ]
        ]
    for edge in [(0, 1), (0, 2), (0, 3), (3, 4), (3, 5)]:
        g.add_pipe(nodes[edge[0]], nodes[edge[1]])

    d = 2 * k if shape == "H" and convention.name == "fixed_boundary" else 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=3,
        debug_output_dir="debug",
        detector_db=detector_db,
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "observable_basis"),
    tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z))),
)
def test_compile_three_cnots(
    convention: Convention, observable_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = three_cnots(observable_basis)
    d = 2 * k + 1 if convention.name == "fixed_bulk" or observable_basis == Basis.X else 2 * k
    generate_circuit_and_assert(
        g, k, convention, expected_distance=d, expected_num_observables=3, detector_db=detector_db
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("k", "convention", "observable_basis"),
    tuple(generate_inputs(CONVENTIONS, (Basis.X, Basis.Z))),
)
def test_compile_steane_encoding(
    convention: Convention, observable_basis: Basis, k: int, detector_db: DetectorDatabase
) -> None:
    g = steane_encoding(observable_basis)
    d = 2 * k + 1 if convention.name == "fixed_bulk" else 2 * k
    expected_num_observables = 3 if observable_basis == Basis.X else 4

    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_observables=expected_num_observables,
        detector_db=detector_db,
    )


@pytest.mark.parametrize(
    ("k", "convention", "kind", "block_temporal_height"),
    tuple(
        generate_inputs(
            CONVENTIONS,
            ("ZXZ", "ZXX", "XZX", "XZZ"),
            (
                LinearFunction(2, -1),
                LinearFunction(3, -1),
                LinearFunction(5, -1),
                LinearFunction(4, 3),
            ),
        )
    ),
)
def test_compile_memory_custom_temporal_height(
    convention: Convention,
    kind: str,
    k: int,
    block_temporal_height: LinearFunction,
    detector_db: DetectorDatabase,
) -> None:
    g = BlockGraph("Memory Experiment")
    g.add_cube(Position3D(0, 0, 0), kind)

    d = 2 * k + 1
    generate_circuit_and_assert(
        g,
        k,
        convention,
        expected_distance=d,
        expected_num_detectors=(d**2 - 1) * int(block_temporal_height(k) + 2),
        expected_num_observables=1,
        block_temporal_height=block_temporal_height,
        detector_db=detector_db,
    )


def _stacked_l_spatial_junction_corners(num_corners: int = 2, mirrored: bool = False) -> BlockGraph:
    """Return ``num_corners`` identical L-shaped spatial-junction memories stacked in time.

    None of the corners are connected by a temporal pipe, so every data qubit
    is reset in the X basis at the start of each corner. This is the minimal
    reproduction of https://github.com/tqec/tqec/issues/1062: a detector
    computed at the boundary between two consecutive corners used to match
    measurements across that reset, resulting in a detector with a ~50%
    firing rate in a noiseless circuit.

    Args:
        num_corners: number of L-shaped corners to stack on top of each other
            (along the z/time axis), with no temporal pipe between them.
        mirrored: if ``True``, both arms extend in the +x/+y directions from
            the corner instead of -x/-y, putting the spatial-junction corner
            (and the invalid detector's border-qubit boundary, if the fix
            were not general) on the opposite side of the sub-template
            window. Used to check that the fix does not depend on which
            specific corner of the sub-template a spatial junction happens
            to sit in.

    """
    x_arm_position, y_arm_position = ((2, 1), (1, 2)) if mirrored else ((0, 1), (1, 0))
    g = BlockGraph("Stacked L Spatial Junction Corners")
    for z in range(num_corners):
        x_arm = g.add_cube(Position3D(*x_arm_position, z), "XZX")
        corner = g.add_cube(Position3D(1, 1, z), "ZZX")
        y_arm = g.add_cube(Position3D(*y_arm_position, z), "ZXX")
        g.add_pipe(x_arm, corner)
        g.add_pipe(corner, y_arm)
    return g


def _assert_all_detectors_deterministic(circuit: stim.Circuit) -> None:
    """Assert that every detector in ``circuit`` is exactly deterministic.

    This is not a sampling-based check: :meth:`stim.Circuit.detector_error_model`
    (called with its default ``allow_gauge_detectors=False``) raises a
    ``ValueError`` if any detector is not a deterministic function of the
    measurements it is built from, using ``stim``'s exact stabilizer-flow
    analysis.
    """
    circuit.detector_error_model(decompose_errors=False)


# (k, manhattan_radius, reschedule_measurements, mirrored, convention).
# This deliberately does not test every combination: the issue demonstrates
# that both very small and (perhaps counter-intuitively) larger radii can be
# affected, that the bug is independent of measurement scheduling, and that
# it is not tied to one specific arm orientation of the corner, so each of
# those axes is exercised at least once, without a full combinatorial sweep.
_STACKED_CORNERS_CASES = (
    pytest.param(1, 2, True, False, FIXED_BULK_CONVENTION, id="k1-r2-resched-bulk"),
    pytest.param(1, 3, True, False, FIXED_BULK_CONVENTION, id="k1-r3-resched-bulk"),
    pytest.param(1, 4, True, False, FIXED_BULK_CONVENTION, id="k1-r4-resched-bulk"),
    pytest.param(1, 2, False, False, FIXED_BULK_CONVENTION, id="k1-r2-noresched-bulk"),
    pytest.param(1, 2, True, True, FIXED_BULK_CONVENTION, id="k1-r2-resched-mirrored-bulk"),
    pytest.param(1, 2, True, False, FIXED_BOUNDARY_CONVENTION, id="k1-r2-resched-boundary"),
    pytest.param(
        2, 2, True, False, FIXED_BULK_CONVENTION, marks=pytest.mark.slow, id="k2-r2-resched-bulk"
    ),
    pytest.param(
        2, 3, True, False, FIXED_BULK_CONVENTION, marks=pytest.mark.slow, id="k2-r3-resched-bulk"
    ),
)


@pytest.mark.parametrize(
    ("k", "manhattan_radius", "reschedule_measurements", "mirrored", "convention"),
    _STACKED_CORNERS_CASES,
)
def test_compile_stacked_l_spatial_junction_corners_has_no_non_deterministic_detector(
    k: int,
    manhattan_radius: int,
    reschedule_measurements: bool,
    mirrored: bool,
    convention: Convention,
    detector_db: DetectorDatabase,
) -> None:
    """Regression test for https://github.com/tqec/tqec/issues/1062.

    Covers, without a full combinatorial sweep: several ``manhattan_radius``
    values (the issue explicitly shows that radius 3 still fails and that
    radius 4, while it happens to hide *this* minimal reproduction, is not a
    general solution -- see
    ``test_compile_three_stacked_l_spatial_junction_corners_has_no_non_deterministic_detector``
    below), both values of ``reschedule_measurements``, a mirrored corner
    orientation, both boundary conventions, and ``k=2`` (which produces a
    ``REPEAT``-containing circuit, exercising a different code path in
    ``remove_non_deterministic_detectors`` than the ``k=1``, loop-free case).
    """
    g = _stacked_l_spatial_junction_corners(num_corners=2, mirrored=mirrored)
    compiled_graph = compile_block_graph(g, convention, observables=None)
    circuit = compiled_graph.generate_stim_circuit(
        k=k,
        manhattan_radius=manhattan_radius,
        detector_database=detector_db,
        database_path=None,
        reschedule_measurements=reschedule_measurements,
    )
    _assert_all_detectors_deterministic(circuit)


@pytest.mark.slow
def test_compile_three_stacked_l_spatial_junction_corners_has_no_non_deterministic_detector(
    detector_db: DetectorDatabase,
) -> None:
    """Larger regression test for https://github.com/tqec/tqec/issues/1062.

    The issue reports that increasing ``manhattan_radius`` to work around the
    minimal 2-corners reproduction can hide the bug for that specific graph
    while still leaving it present for a larger one. This test stacks three
    corners (instead of two) at ``manhattan_radius=4`` -- the radius that
    hides the bug for the 2-corners case above -- specifically to prove that
    the fix is not merely filtering the one detector from the minimal
    reproduction: a fix that only special-cased that exact detector, graph,
    or radius would pass every other test in this module while still failing
    here.
    """
    g = _stacked_l_spatial_junction_corners(num_corners=3)
    compiled_graph = compile_block_graph(g, observables=None)
    circuit = compiled_graph.generate_stim_circuit(
        k=1, manhattan_radius=4, detector_database=detector_db, database_path=None
    )
    _assert_all_detectors_deterministic(circuit)


def test_compile_stacked_l_spatial_junction_corners_streaming_matches_non_streaming(
    detector_db: DetectorDatabase,
) -> None:
    """Streaming regression test for https://github.com/tqec/tqec/issues/1062.

    ``CompiledGraph.generate_stim_circuit_stream`` cannot run the final,
    exact non-determinism check that ``generate_stim_circuit`` runs, because
    that check needs the fully assembled circuit (see the ``Warning`` section
    of both methods' docstrings for why). This test checks that the
    documented workaround actually restores the same guarantee: reassembling
    the streamed chunks and calling
    :func:`~tqec.compile.detectors.detector.remove_non_deterministic_detectors`
    on the result removes the exact same non-deterministic detector that
    ``generate_stim_circuit`` removes automatically, so a caller who does
    need the guarantee while streaming is not left without a way to get it.
    """
    g = _stacked_l_spatial_junction_corners(num_corners=2)
    compiled_graph = compile_block_graph(g, observables=None)

    streamed_circuit = stim.Circuit()
    for chunk in compiled_graph.generate_stim_circuit_stream(
        k=1, detector_database=detector_db, database_path=None
    ):
        streamed_circuit += chunk
    # The raw, reassembled streamed circuit is expected to still contain the
    # non-deterministic detector: this is the documented limitation, not a
    # regression, and this assertion protects against silently "fixing" the
    # streaming path without updating its documentation.
    with pytest.raises(ValueError):
        _assert_all_detectors_deterministic(streamed_circuit)

    cleaned_circuit = remove_non_deterministic_detectors(streamed_circuit)
    _assert_all_detectors_deterministic(cleaned_circuit)

    non_streamed_circuit = compiled_graph.generate_stim_circuit(
        k=1, detector_database=detector_db, database_path=None
    )
    assert cleaned_circuit.num_detectors == non_streamed_circuit.num_detectors
