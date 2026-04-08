import pytest

from tqec.compile.specs.enums import SpatialArms
from tqec.compile.specs.library.generators.fixed_boundary import FixedBoundaryConventionGenerator
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis, Orientation


@pytest.fixture(scope="session", name="translator")
def fixture_rpng_translator():
    return DefaultRPNGTranslator()


@pytest.fixture(scope="session", name="generator")
def fixture_generator(translator):
    compiler = IdentityPlaquetteCompiler
    return FixedBoundaryConventionGenerator(translator, compiler)


def _assert_result_contains_bases_and_orientations(
    result: dict[Basis, dict[Orientation, RPNGDescription]],
):
    assert Basis.X in result and Basis.Z in result
    assert Orientation.VERTICAL in result[Basis.X] and Orientation.HORIZONTAL in result[Basis.X]


def test_get_bulk_rpng_descriptions(generator):
    result = generator.get_bulk_rpng_descriptions(is_reversed=True)
    _assert_result_contains_bases_and_orientations(result)


def test_get_3_body_rpng_descriptions(generator):
    result = generator.get_3_body_rpng_descriptions(basis=Basis.X, is_reversed=False)
    assert len(result) == 4


def test_get_2_body_rpng_descriptions(generator):
    result = generator.get_2_body_rpng_descriptions(is_reversed=True)
    assert Basis.X in result and len(result[Basis.X]) == 4
    assert Basis.Z in result and len(result[Basis.Z]) == 4


def test_get_extended_plaquettes(generator):
    result = generator.get_extended_plaquettes(
        reset=Basis.X, measurement=Basis.X, is_reversed=False
    )
    assert Basis.X in result and Basis.Z in result


def test_get_bulk_hadamard_rpng_descriptions(generator):
    result = generator.get_bulk_hadamard_rpng_descriptions(is_reversed=False)
    _assert_result_contains_bases_and_orientations(result)


def test_get_memory_horizontal_boundary_rpng_descriptions(generator):
    result = generator.get_memory_horizontal_boundary_rpng_descriptions(is_reversed=False)
    assert len(result) == 6


def test_get_spatial_x_hadamard_rpng_descriptions(generator):
    result = generator.get_spatial_x_hadamard_rpng_descriptions(
        top_left_basis=Basis.X, is_reversed=False
    )
    assert len(result) == 3


def test_get_spatial_y_hadamard_rpng_descriptions(generator):
    result = generator.get_spatial_y_hadamard_rpng_descriptions(
        top_left_basis=Basis.X, is_reversed=False
    )
    assert len(result) == 3


def test_get_memory_qubit_rpng_descriptions(generator):
    result = generator.get_memory_qubit_rpng_descriptions(is_reversed=False)
    assert len(result) == 6


def test_get_memory_vertical_boundary_rpng_descriptions(generator):
    result = generator.get_memory_vertical_boundary_rpng_descriptions(is_reversed=False)
    assert len(result) == 6


def test_get_spatial_cube_qubit_rpng_descriptions_none_spatial_arms(generator):
    result = generator.get_spatial_cube_qubit_rpng_descriptions(
        spatial_boundary_basis=Basis.X, arms=SpatialArms.NONE, is_reversed=True
    )
    assert len(result) == 16
    assert str(result[5]) == "---- -x3- -x4- -x1-"


def test_get_spatial_cube_qubit_rpng_descriptions(generator):
    result = generator.get_spatial_cube_qubit_rpng_descriptions(
        spatial_boundary_basis=Basis.X, arms=SpatialArms.RIGHT, is_reversed=True
    )
    assert len(result) == 15


def test_get_temporal_hadamard_rpng_descriptions(generator):
    result = generator.get_temporal_hadamard_rpng_descriptions(is_reversed=False)
    assert len(result) == 6


def test_get_spatial_vertical_hadamard_rpng_descriptions(generator):
    result = generator.get_spatial_vertical_hadamard_rpng_descriptions(
        top_left_basis=Basis.X, is_reversed=False
    )
    assert len(result) == 6


def test_get_spatial_horizontal_hadamard_rpng_descriptions(generator):
    result = generator.get_spatial_horizontal_hadamard_rpng_descriptions(
        top_left_basis=Basis.X, is_reversed=False
    )
    assert len(result) == 6
