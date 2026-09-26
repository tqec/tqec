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
from functools import partial
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

import numpy
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
from tqec.compile.detectors.exact import _deterministic_checks, _strip_annotations
from tqec.compile.detectors.open_boundary import build_open_boundary_analysis_circuit
from tqec.compile.detectors.space import GF2Basis
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery import memory
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


def _generate_circuit_and_assert(
    g: BlockGraph,
    k: int,
    convention: Convention,
    expected_distance: int | None = None,
    expected_num_detectors: int | None = None,
    expected_num_observables: int | None = None,
    debug_output_dir: str | Path | None = None,
    block_temporal_height: LinearFunction = _DEFAULT_BLOCK_REPETITIONS,
    detector_db: DetectorDatabase | None = None,
    detector_backend: Literal["local", "exact"] = "local",
    ignore_ungraphlike_errors: bool = False,
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
    circuit = layer_tree.generate_circuit(
        k,
        detector_database=detector_db,
        database_path=None,
        detector_backend=detector_backend,
    )
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
        ignore_ungraphlike_errors=ignore_ungraphlike_errors,
        canonicalize_circuit_errors=True,
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


@pytest.fixture(params=("local", "exact"))
def detector_backend(request: pytest.FixtureRequest) -> Literal["local", "exact"]:
    return request.param


@pytest.fixture
def generate_circuit_and_assert(
    detector_db: DetectorDatabase,
    detector_backend: Literal["local", "exact"],
):
    return partial(
        _generate_circuit_and_assert,
        detector_db=detector_db,
        detector_backend=detector_backend,
    )


@pytest.fixture(scope="session", autouse=True)
def save_to_db(
    filepath: Path,
    detector_db: DetectorDatabase,
):
    yield
    detector_db.to_file(filepath)


@pytest.mark.parametrize(
    ("k", "convention", "kind"),
    tuple(generate_inputs(CONVENTIONS, ("ZXZ", "ZXX", "XZX", "XZZ"))),
)
def test_compile_memory(
    convention: Convention,
    kind: str,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    kind: str,
    k: int,
    xy: tuple[int, int],
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    kinds: tuple[str, str],
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    kinds: tuple[str, str],
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    k: int,
    in_future: bool,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    in_obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    h_top_obs_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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


def test_compile_stacked_spatial_junction_corners_filters_invalid_detectors(
    detector_db: DetectorDatabase,
) -> None:
    graph = BlockGraph("Stacked Spatial Junction Corners")
    for z in (0, 1):
        left = Position3D(0, 1, z)
        corner = Position3D(1, 1, z)
        bottom = Position3D(1, 0, z)
        graph.add_cube(left, ZXCube.from_str("XZX"))
        graph.add_cube(corner, ZXCube.from_str("ZZX"))
        graph.add_cube(bottom, ZXCube.from_str("ZXX"))
        graph.add_pipe(left, corner)
        graph.add_pipe(corner, bottom)

    tree = compile_block_graph(graph, observables=None).to_layer_tree()
    local = tree.generate_circuit(1, database_path=None, detector_database=detector_db)
    checks, _ = _deterministic_checks(local)
    deterministic = GF2Basis(checks)
    bad = [
        c.measurements
        for c in _strip_annotations(local)[1]
        if not deterministic.contains(c.measurements)
    ]
    assert bad
    exact = tree.generate_circuit(1, database_path=None, detector_backend="exact")
    kept = {c.measurements for c in _strip_annotations(exact)[1]}
    assert not kept.intersection(bad)
    assert all(deterministic.contains(row) for row in kept)
    exact.detector_error_model(allow_gauge_detectors=False, decompose_errors=False)
    assert not numpy.asarray(exact.compile_detector_sampler().sample(32)).any()


@pytest.mark.parametrize("k,local_rank,exact_rank", [(1, 109, 110), (2, 512, 514)])
def test_compile_future_temporal_port_junction_completes_syndrome_space(
    k: int,
    local_rank: int,
    exact_rank: int,
    detector_db: DetectorDatabase,
) -> None:
    graph = BlockGraph("Junction with a Future Temporal Port")
    junction = Position3D(0, 0, 0)
    arm = Position3D(0, 1, 0)
    spatial_port = Position3D(-1, 0, 0)
    temporal_port = Position3D(0, 1, 1)
    graph.add_cube(junction, "XXZ")
    graph.add_cube(arm, "XZZ")
    graph.add_pipe(junction, arm)
    graph.add_cube(spatial_port, "P", "SpatialPort")
    graph.add_pipe(junction, spatial_port)
    graph.add_cube(temporal_port, "P", "TemporalPort")
    graph.add_pipe(arm, temporal_port)
    graph.fill_ports(
        {
            "SpatialPort": ZXCube.from_str("ZXZ"),
            "TemporalPort": ZXCube.from_str("XZZ"),
        }
    )

    tree = compile_block_graph(graph, FIXED_BOUNDARY_CONVENTION).to_layer_tree()
    local = tree.generate_circuit(k, database_path=None, detector_database=detector_db)
    exact = tree.generate_circuit(
        k, database_path=None, detector_database=detector_db, detector_backend="exact"
    )
    local_space = GF2Basis(c.measurements for c in _strip_annotations(local)[1])
    exact_space = GF2Basis(c.measurements for c in _strip_annotations(exact)[1])
    checks, _ = _deterministic_checks(exact)
    assert local_space.rank == local_rank
    assert tree._logical_observables is not None
    assert exact_space.rank == len(checks) - len(tree._logical_observables) == exact_rank
    assert all(exact_space.contains(row) for row in local_space.rows)

    assert local.num_detectors == local_rank
    assert exact.num_detectors == exact_rank
    assert local.num_observables == exact.num_observables == 1
    if k == 2:
        # Graphlike distance checks the quality of the chosen detector basis.
        for circuit, expected_distance in [(local, 2), (exact, 5)]:
            noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(circuit)
            assert (
                len(noisy.shortest_graphlike_error(ignore_ungraphlike_errors=True))
                == expected_distance
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
    convention: Convention,
    direction: Direction3D,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    generate_circuit_and_assert,
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
    convention: Convention,
    shape: str,
    basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    shape: str,
    spatial_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    kind: str,
    direction: Direction3D,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    kind: str,
    shape: str,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    shape: str,
    spatial_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    observable_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    convention: Convention,
    observable_basis: Basis,
    k: int,
    detector_db: DetectorDatabase,
    generate_circuit_and_assert,
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
    generate_circuit_and_assert,
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


@pytest.mark.parametrize("factory", [memory, cnot, move_rotation, three_cnots])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
@pytest.mark.parametrize("convention", [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION])
def test_complete_logical_semantics_are_independent_of_emission(factory, basis, convention) -> None:
    graph = factory(basis)
    selected = graph.find_correlation_surfaces()[:1]
    spaces = []
    for observables in [None, selected, "auto"]:
        tree = compile_block_graph(graph, convention, observables).to_layer_tree()
        with patch.object(BlockGraph, "find_correlation_surfaces", side_effect=AssertionError):
            circuit = tree.generate_circuit(
                1, database_path=None, manhattan_radius=0, detector_backend="exact"
            )
        analysis = build_open_boundary_analysis_circuit(tree, 1, circuit)
        supports = analysis.logical_supports
        if observables == "auto":
            emitted = _strip_annotations(circuit)[2]
            assert tuple(emitted[i] for i in range(len(supports))) == supports
        checks, _ = _deterministic_checks(circuit)
        space = GF2Basis(c.measurements for c in _strip_annotations(circuit)[1])
        assert space.rank == len(checks) - len(supports)
        assert tree._logical_observables is not None
        assert circuit.num_observables == (
            0
            if observables is None
            else len(selected if observables != "auto" else tree._logical_observables)
        )
        assert not numpy.asarray(circuit.compile_detector_sampler().sample(16)).any()
        spaces.append(space)
    assert all(space.rank == spaces[0].rank for space in spaces)
    assert all(spaces[0].contains(row) for space in spaces for row in space.rows)


def test_discovery_runs_once_after_normalization() -> None:
    graph = cnot(Basis.Z).shift_by(dz=3)
    calls = []
    original = BlockGraph.find_correlation_surfaces

    def discover(normalized, *args, **kwargs):
        calls.append(normalized)
        return original(normalized, *args, **kwargs)

    with patch.object(BlockGraph, "find_correlation_surfaces", discover):
        compiled = compile_block_graph(graph, observables=None)
        compiled.generate_stim_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert len(calls) == 1
    assert min(c.position.z for c in calls[0].cubes) == 0


def test_incomplete_external_generators_disable_completion() -> None:
    tree = compile_block_graph(memory()).to_layer_tree()
    assert tree._logical_surfaces is not None
    tree._logical_surfaces *= 2
    with pytest.warns(UserWarning, match="completion disabled"):
        circuit = tree.generate_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert circuit.num_detectors == 0


@pytest.mark.parametrize("observables", [None, "auto"])
def test_unavailable_discovery_allows_filtering_without_completion(observables) -> None:
    with patch.object(BlockGraph, "find_correlation_surfaces", side_effect=NotImplementedError):
        with pytest.warns(UserWarning, match="Full logical semantics unavailable"):
            tree = compile_block_graph(memory(), observables=observables).to_layer_tree()
    circuit = tree.generate_circuit(
        1, manhattan_radius=0, database_path=None, detector_backend="exact"
    )
    assert circuit.num_detectors == 0
    assert tree._logical_observables is None


@pytest.mark.parametrize("factory", [memory, cnot])
@pytest.mark.parametrize("basis", [Basis.X, Basis.Z])
def test_successful_exact_backend_analyzes_flows_once(factory, basis) -> None:
    tree = compile_block_graph(factory(basis)).to_layer_tree()
    original = stim.Circuit.flow_generators
    calls = []

    def analyze(circuit):
        calls.append(circuit)
        return original(circuit)

    with patch.object(stim.Circuit, "flow_generators", analyze):
        circuit = tree.generate_circuit(
            1, manhattan_radius=0, database_path=None, detector_backend="exact"
        )
    assert len(calls) == 1
    assert calls[0].num_qubits > circuit.num_qubits
    assert circuit.num_detectors > 0
    local = tree.generate_circuit(1, manhattan_radius=0, database_path=None)
    assert _strip_annotations(circuit)[0] == _strip_annotations(local)[0]
