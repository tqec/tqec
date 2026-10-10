import pytest

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.specs.base import CubeSpec, PipeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.fixed_bulk import FixedBulkCubeBuilder, FixedBulkPipeBuilder
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitSpatialCubeTemplate, QubitTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.scale import LinearFunction


@pytest.fixture
def cube_builder() -> FixedBulkCubeBuilder:
    return FixedBulkCubeBuilder(IdentityPlaquetteCompiler)


@pytest.fixture
def pipe_builder() -> FixedBulkPipeBuilder:
    return FixedBulkPipeBuilder(IdentityPlaquetteCompiler)


def _assert_alternating_block(block: Block, expected_measurement: Plaquettes) -> None:
    assert len(block.layer_sequence) == 3
    repeated_layers = block.layer_sequence[1]
    assert isinstance(repeated_layers, SequencedLayers)
    repeated_alternation = repeated_layers.layer_sequence[0]
    assert isinstance(repeated_alternation, RepeatedLayer)
    assert isinstance(repeated_alternation.internal_layer, SequencedLayers)
    reversed_layer, forward_layer = repeated_alternation.internal_layer.layer_sequence
    assert isinstance(reversed_layer, PlaquetteLayer)
    assert isinstance(forward_layer, PlaquetteLayer)
    assert reversed_layer.plaquettes.to_name_dict() != forward_layer.plaquettes.to_name_dict()

    measurement_layer = block.layer_sequence[-1]
    assert isinstance(measurement_layer, PlaquetteLayer)
    assert measurement_layer.plaquettes.to_name_dict() == expected_measurement.to_name_dict()


def _expected_cube_measurement(
    builder: FixedBulkCubeBuilder, spec: CubeSpec, is_reversed: bool
) -> Plaquettes:
    kind = spec.kind
    assert isinstance(kind, ZXCube)
    if spec.is_spatial:
        return builder._generator.get_spatial_cube_qubit_plaquettes(
            kind.x, spec.spatial_arms, is_reversed, None, kind.z
        )
    orientation = Orientation.HORIZONTAL if kind.x == Basis.Z else Orientation.VERTICAL
    return builder._generator.get_memory_qubit_plaquettes(is_reversed, orientation, None, kind.z)


@pytest.mark.parametrize(
    "cube_spec",
    [
        CubeSpec(ZXCube.XZZ, has_spatial_up_or_down_pipe_in_timeslice=True),
        CubeSpec(
            ZXCube.XXZ,
            SpatialArms.UP | SpatialArms.RIGHT,
            has_spatial_up_or_down_pipe_in_timeslice=True,
        ),
    ],
)
@pytest.mark.parametrize(("offset", "measurement_is_reversed"), [(2, True), (3, False)])
def test_fixed_bulk_cube_builder_alternates_schedules(
    cube_builder: FixedBulkCubeBuilder,
    cube_spec: CubeSpec,
    offset: int,
    measurement_is_reversed: bool,
) -> None:
    block = cube_builder(cube_spec, LinearFunction(4, offset))

    _assert_alternating_block(
        block,
        _expected_cube_measurement(cube_builder, cube_spec, measurement_is_reversed),
    )


def _expected_pipe_measurement(
    builder: FixedBulkPipeBuilder, spec: PipeSpec, is_reversed: bool
) -> Plaquettes:
    if any(cube.is_spatial for cube in spec.cube_specs):
        pipe_kind = spec.pipe_kind
        spatial_boundary_basis = pipe_kind.x if pipe_kind.x is not None else pipe_kind.y
        assert spatial_boundary_basis is not None
        arms = FixedBulkPipeBuilder._get_spatial_cube_arms(spec)
        return builder._generator.get_spatial_cube_arm_plaquettes(
            spatial_boundary_basis,
            arms,
            spec.cube_specs,
            is_reversed,
            None,
            pipe_kind.z,
            pipe_kind.has_hadamard,
        )

    pipe_kind = spec.pipe_kind
    if pipe_kind.direction == Direction3D.X:
        z_orientation = Orientation.HORIZONTAL if pipe_kind.y == Basis.X else Orientation.VERTICAL
        return builder._generator.get_memory_vertical_boundary_plaquettes(
            is_reversed, z_orientation, None, pipe_kind.z
        )
    z_orientation = Orientation.HORIZONTAL if pipe_kind.x == Basis.Z else Orientation.VERTICAL
    return builder._generator.get_memory_horizontal_boundary_plaquettes(
        is_reversed, z_orientation, None, pipe_kind.z
    )


def _spatial_pipe_specs() -> tuple[PipeSpec, PipeSpec]:
    pipe_kind = PipeKind.from_str("OXZ")
    regular_cube = CubeSpec(ZXCube.ZXZ)
    regular_pipe = PipeSpec(
        (regular_cube, regular_cube),
        (QubitTemplate(), QubitTemplate()),
        pipe_kind,
        has_spatial_up_or_down_pipe_in_timeslice=True,
    )

    left_spatial_cube = CubeSpec(ZXCube.XXZ, SpatialArms.RIGHT)
    right_spatial_cube = CubeSpec(ZXCube.XXZ, SpatialArms.LEFT)
    spatial_cube_pipe = PipeSpec(
        (left_spatial_cube, right_spatial_cube),
        (QubitSpatialCubeTemplate(), QubitSpatialCubeTemplate()),
        pipe_kind,
        has_spatial_up_or_down_pipe_in_timeslice=True,
    )
    return regular_pipe, spatial_cube_pipe


@pytest.mark.parametrize("spec", _spatial_pipe_specs())
@pytest.mark.parametrize(("offset", "measurement_is_reversed"), [(2, True), (3, False)])
def test_fixed_bulk_spatial_pipe_builder_alternates_schedules(
    pipe_builder: FixedBulkPipeBuilder,
    spec: PipeSpec,
    offset: int,
    measurement_is_reversed: bool,
) -> None:
    block = pipe_builder(spec, LinearFunction(4, offset))

    _assert_alternating_block(
        block,
        _expected_pipe_measurement(pipe_builder, spec, measurement_is_reversed),
    )


def test_fixed_bulk_L_junction_dem_is_deterministic() -> None:
    """Compile a fixed-bulk L-junction at k=2, 3 repetitions and check the DEM.

    This test ensures that the noiseless detector error model can be built
    without raising a nondeterminism error, and that it contains detectors.
    It is a regression guard for the schedule-parity alternation introduced in
    the fixed-bulk convention.
    """
    # Build an L-shaped spatial junction: ZXX -- ZZX -- XZX
    g = BlockGraph("L Spatial Junction")
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXX")
    n2 = g.add_cube(Position3D(0, 1, 0), "ZZX")
    n3 = g.add_cube(Position3D(1, 1, 0), "XZX")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)

    k = 2
    # At k=2, the default block_temporal_height = LinearFunction(2, -1)
    # evaluates to 2 * 2 - 1 = 3 repetitions.
    compiled = compile_block_graph(g, FIXED_BULK_CONVENTION)
    layer_tree = compiled.to_layer_tree()
    circuit = layer_tree.generate_circuit(
        k, detector_database=DetectorDatabase(), database_path=None
    )

    # detector_error_model() raises if the circuit is nondeterministic.
    dem = circuit.detector_error_model()
    assert dem.num_detectors > 0
