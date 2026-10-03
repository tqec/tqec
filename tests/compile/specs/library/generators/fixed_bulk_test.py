import pytest
import stim

from tqec.compile.generation import generate_circuit
from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.fixed_bulk import (
    FixedBulkConventionGenerator,
    make_fixed_bulk_realignment_plaquette,
)
from tqec.computation.cube import ZXCube
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.qubit import QubitSpatialCubeTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict


@pytest.fixture(scope="session", name="translator")
def fixture_rpng_translator():
    return DefaultRPNGTranslator()


@pytest.fixture(scope="session", name="generator")
def fixture_generator(translator):
    compiler = IdentityPlaquetteCompiler
    return FixedBulkConventionGenerator(translator, compiler)


def test_fixed_bulk_realignment_plaquette() -> None:
    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.X,
        z_orientation=Orientation.VERTICAL,
        mq_reset=Basis.X,
        mq_measurement=Basis.Z,
        debug_basis=PauliBasis.X,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RX 4
TICK
CX 4 0
TICK
TICK
CX 4 2
TICK
CX 1 4
TICK
CX 0 4
TICK
MZ 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_polygons() == PauliBasis.X

    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.Z,
        z_orientation=Orientation.HORIZONTAL,
        mq_reset=Basis.Z,
        mq_measurement=Basis.X,
        debug_basis=PauliBasis.Z,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RZ 4
TICK
CX 0 4
TICK
TICK
CX 2 4
TICK
CX 4 1
TICK
CX 4 0
TICK
MX 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_polygons() == PauliBasis.Z


def test_get_bulk_rpng_descriptions(generator: FixedBulkConventionGenerator) -> None:
    # Regression check for is_reversed=False
    fwd = generator.get_bulk_rpng_descriptions(is_reversed=False)
    assert str(fwd[Basis.X][Orientation.VERTICAL]) == "-x1- -x4- -x3- -x5-"
    assert str(fwd[Basis.X][Orientation.HORIZONTAL]) == "-x1- -x2- -x3- -x5-"
    assert str(fwd[Basis.Z][Orientation.VERTICAL]) == "-z1- -z4- -z3- -z5-"
    assert str(fwd[Basis.Z][Orientation.HORIZONTAL]) == "-z1- -z2- -z3- -z5-"

    # Check for is_reversed=True
    rev = generator.get_bulk_rpng_descriptions(is_reversed=True)
    assert str(rev[Basis.X][Orientation.VERTICAL]) == "-x5- -x3- -x4- -x1-"
    assert str(rev[Basis.X][Orientation.HORIZONTAL]) == "-x5- -x3- -x2- -x1-"
    assert str(rev[Basis.Z][Orientation.VERTICAL]) == "-z5- -z3- -z4- -z1-"
    assert str(rev[Basis.Z][Orientation.HORIZONTAL]) == "-z5- -z3- -z2- -z1-"

    # Check with reset and measurement
    rev_rm = generator.get_bulk_rpng_descriptions(
        is_reversed=True, reset=Basis.X, measurement=Basis.Z
    )
    assert str(rev_rm[Basis.X][Orientation.VERTICAL]) == "xx5z xx3z xx4z xx1z"


def test_get_3_body_rpng_descriptions(generator: FixedBulkConventionGenerator) -> None:
    # Regression check for is_reversed=False
    fwd = generator.get_3_body_rpng_descriptions(is_reversed=False)
    assert str(fwd[0]) == "---- -z4- -z3- -z5-"
    assert str(fwd[1]) == "-x1- ---- -x3- -x5-"
    assert str(fwd[2]) == "-x1- -x2- ---- -x5-"
    assert str(fwd[3]) == "-z1- -z4- -z3- ----"

    # Check for is_reversed=True
    rev = generator.get_3_body_rpng_descriptions(is_reversed=True)
    assert str(rev[0]) == "---- -z3- -z4- -z1-"
    assert str(rev[1]) == "-x5- ---- -x2- -x1-"
    assert str(rev[2]) == "-x5- -x3- ---- -x1-"
    assert str(rev[3]) == "-z5- -z3- -z4- ----"

    # Check with reset and measurement
    rev_rm = generator.get_3_body_rpng_descriptions(
        is_reversed=True, reset=Basis.X, measurement=Basis.Z
    )
    assert str(rev_rm[0]) == "---- xz3z xz4z xz1z"


def test_get_2_body_rpng_descriptions(generator: FixedBulkConventionGenerator) -> None:
    # Regression check for is_reversed=False
    fwd = generator.get_2_body_rpng_descriptions(is_reversed=False)
    assert str(fwd[Basis.X][PlaquetteOrientation.DOWN]) == "-x1- -x2- ---- ----"
    assert str(fwd[Basis.X][PlaquetteOrientation.LEFT]) == "---- -x2- ---- -x5-"
    assert str(fwd[Basis.X][PlaquetteOrientation.UP]) == "---- ---- -x3- -x5-"
    assert str(fwd[Basis.X][PlaquetteOrientation.RIGHT]) == "-x1- ---- -x3- ----"

    assert str(fwd[Basis.Z][PlaquetteOrientation.DOWN]) == "-z1- -z2- ---- ----"
    assert str(fwd[Basis.Z][PlaquetteOrientation.LEFT]) == "---- -z2- ---- -z5-"
    assert str(fwd[Basis.Z][PlaquetteOrientation.UP]) == "---- ---- -z3- -z5-"
    assert str(fwd[Basis.Z][PlaquetteOrientation.RIGHT]) == "-z1- ---- -z3- ----"

    # Check for is_reversed=True
    rev = generator.get_2_body_rpng_descriptions(is_reversed=True)
    assert str(rev[Basis.X][PlaquetteOrientation.DOWN]) == "-x5- -x3- ---- ----"
    assert str(rev[Basis.X][PlaquetteOrientation.LEFT]) == "---- -x3- ---- -x1-"
    assert str(rev[Basis.X][PlaquetteOrientation.UP]) == "---- ---- -x2- -x1-"
    assert str(rev[Basis.X][PlaquetteOrientation.RIGHT]) == "-x5- ---- -x2- ----"

    assert str(rev[Basis.Z][PlaquetteOrientation.DOWN]) == "-z5- -z3- ---- ----"
    assert str(rev[Basis.Z][PlaquetteOrientation.LEFT]) == "---- -z3- ---- -z1-"
    assert str(rev[Basis.Z][PlaquetteOrientation.UP]) == "---- ---- -z2- -z1-"
    assert str(rev[Basis.Z][PlaquetteOrientation.RIGHT]) == "-z5- ---- -z2- ----"


def test_get_extended_plaquettes(generator: FixedBulkConventionGenerator) -> None:
    fwd = generator.get_extended_plaquettes(is_reversed=False)
    rev = generator.get_extended_plaquettes(is_reversed=True)
    assert Basis.X in fwd and Basis.Z in fwd
    assert Basis.X in rev and Basis.Z in rev


def test_no_gate_schedule_clash_when_tiling_reversed_plaquettes(
    generator: FixedBulkConventionGenerator,
) -> None:
    template = QubitSpatialCubeTemplate()
    corner_descriptions = generator.get_3_body_rpng_descriptions(is_reversed=True)
    bulk_descriptions = generator.get_bulk_rpng_descriptions(is_reversed=True)
    two_body_descriptions = generator.get_2_body_rpng_descriptions(is_reversed=True)

    for sbb in (Basis.Z, Basis.X):
        boundary_is_z = sbb == Basis.Z
        mapping: dict[int, RPNGDescription] = {}
        if boundary_is_z:
            mapping[10] = two_body_descriptions[sbb][PlaquetteOrientation.UP]
            mapping[21] = two_body_descriptions[sbb][PlaquetteOrientation.RIGHT]
            mapping[23] = two_body_descriptions[sbb][PlaquetteOrientation.DOWN]
            mapping[12] = two_body_descriptions[sbb][PlaquetteOrientation.LEFT]
            mapping[5] = corner_descriptions[0]
            mapping[8] = corner_descriptions[3]
            zup = zdown = Orientation.HORIZONTAL
        else:
            mapping[9] = two_body_descriptions[sbb][PlaquetteOrientation.UP]
            mapping[22] = two_body_descriptions[sbb][PlaquetteOrientation.RIGHT]
            mapping[24] = two_body_descriptions[sbb][PlaquetteOrientation.DOWN]
            mapping[11] = two_body_descriptions[sbb][PlaquetteOrientation.LEFT]
            mapping[6] = corner_descriptions[1]
            mapping[7] = corner_descriptions[2]
            zup = zdown = Orientation.VERTICAL

        zright = zleft = zup.flip()
        xup, xdown, xright, xleft = (zup.flip(), zdown.flip(), zright.flip(), zleft.flip())

        if boundary_is_z:
            mapping[6] = mapping[17] = bulk_descriptions[Basis.X][xup]
            mapping[7] = mapping[19] = bulk_descriptions[Basis.X][xdown]
        else:
            mapping[5] = mapping[13] = bulk_descriptions[Basis.Z][zup]
            mapping[8] = mapping[15] = bulk_descriptions[Basis.Z][zdown]

        mapping[13] = bulk_descriptions[Basis.Z][zup]
        mapping[14] = bulk_descriptions[Basis.Z][zright]
        mapping[15] = bulk_descriptions[Basis.Z][zdown]
        mapping[16] = bulk_descriptions[Basis.Z][zleft]
        mapping[17] = bulk_descriptions[Basis.X][xup]
        mapping[18] = bulk_descriptions[Basis.X][xright]
        mapping[19] = bulk_descriptions[Basis.X][xdown]
        mapping[20] = bulk_descriptions[Basis.X][xleft]

        fdd = FrozenDefaultDict(mapping, default_value=RPNGDescription.empty())
        plqts = Plaquettes(fdd.map_values(generator._mapper.get_plaquette))
        for k in (1, 2, 3):
            # generate_circuit merges all scheduled circuits for all tiled plaquettes.
            # Any collision on any qubit at any timestep would raise ScheduleError.
            circ = generate_circuit(template, k, plqts)
            assert len(circ.schedule) > 0


def test_spatial_forward_plaquettes_match_previous_output(
    generator: FixedBulkConventionGenerator,
) -> None:
    linked_cubes = (CubeSpec(ZXCube.XXZ), CubeSpec(ZXCube.XXZ))
    spatial_cube = generator.get_spatial_cube_qubit_plaquettes(
        Basis.Z, SpatialArms.UP | SpatialArms.RIGHT, is_reversed=False
    )
    left_right_arm = generator.get_spatial_cube_arm_plaquettes(
        Basis.Z, SpatialArms.RIGHT, linked_cubes, is_reversed=False
    )
    up_down_arm = generator.get_spatial_cube_arm_plaquettes(
        Basis.Z, SpatialArms.UP, linked_cubes, is_reversed=False
    )

    assert spatial_cube.to_name_dict() == {
        4: "ID(-z1- -z2- ---- ----)",
        23: "ID(-z1- -z2- ---- ----)",
        1: "ID(---- -z2- ---- -z5-)",
        12: "ID(---- -z2- ---- -z5-)",
        5: "ID(-z1- -z4- -z3- -z5-)",
        13: "ID(-z1- -z4- -z3- -z5-)",
        8: "ID(-z1- -z2- -z3- -z5-)",
        15: "ID(-z1- -z2- -z3- -z5-)",
        14: "ID(-z1- -z2- -z3- -z5-)",
        16: "ID(-z1- -z4- -z3- -z5-)",
        6: "ID(-x1- -x2- -x3- -x5-)",
        17: "ID(-x1- -x2- -x3- -x5-)",
        7: "ID(-x1- -x4- -x3- -x5-)",
        19: "ID(-x1- -x4- -x3- -x5-)",
        18: "ID(-x1- -x4- -x3- -x5-)",
        20: "ID(-x1- -x2- -x3- -x5-)",
        "default": "ID(---- ---- ---- ----)",
    }
    assert left_right_arm.to_name_dict() == {
        2: "ID(---- ---- -z3- -z5-)",
        3: "ID(-z1- -z2- ---- ----)",
        5: "ID(-z1- -z2- -z3- -z5-)",
        6: "ID(-x1- -x4- -x3- -x5-)",
        7: "ID(-x1- -x4- -x3- -x5-)",
        8: "ID(-z1- -z2- -z3- -z5-)",
        "default": "ID(---- ---- ---- ----)",
    }
    assert up_down_arm.to_name_dict() == {
        3: "ID(---- -z2- ---- -z5-)",
        2: "ID(-z1- ---- -z3- ----)",
        5: "ID(-z1- -z4- -z3- -z5-)",
        6: "ID(-x1- -x2- -x3- -x5-)",
        7: "ID(-x1- -x2- -x3- -x5-)",
        8: "ID(-z1- -z4- -z3- -z5-)",
        "default": "ID(---- ---- ---- ----)",
    }


def test_reversed_spatial_plaquettes_are_clash_free(
    generator: FixedBulkConventionGenerator,
) -> None:
    linked_cubes = (CubeSpec(ZXCube.XXZ), CubeSpec(ZXCube.XXZ))
    configurations = (
        (
            generator.get_spatial_cube_qubit_raw_template(),
            generator.get_spatial_cube_qubit_plaquettes(
                Basis.Z, SpatialArms.UP | SpatialArms.RIGHT, is_reversed=False
            ),
            generator.get_spatial_cube_qubit_plaquettes(
                Basis.Z, SpatialArms.UP | SpatialArms.RIGHT, is_reversed=True
            ),
        ),
        (
            generator.get_spatial_cube_arm_raw_template(SpatialArms.RIGHT),
            generator.get_spatial_cube_arm_plaquettes(
                Basis.Z, SpatialArms.RIGHT, linked_cubes, is_reversed=False
            ),
            generator.get_spatial_cube_arm_plaquettes(
                Basis.Z, SpatialArms.RIGHT, linked_cubes, is_reversed=True
            ),
        ),
        (
            generator.get_spatial_cube_arm_raw_template(SpatialArms.UP),
            generator.get_spatial_cube_arm_plaquettes(
                Basis.Z, SpatialArms.UP, linked_cubes, is_reversed=False
            ),
            generator.get_spatial_cube_arm_plaquettes(
                Basis.Z, SpatialArms.UP, linked_cubes, is_reversed=True
            ),
        ),
    )

    for template, forward, reversed_plaquettes in configurations:
        assert forward != reversed_plaquettes
        for k in (1, 2, 3):
            circuit = generate_circuit(template, k, reversed_plaquettes)
            assert len(circuit.schedule) > 0
