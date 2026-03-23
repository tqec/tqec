import pytest

from tqec.compile.specs.library.generators.fixed_boundary import FixedBoundaryConventionGenerator
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis


@pytest.fixture(scope="session", name="translator")
def fixture_rpng_translator():
    return DefaultRPNGTranslator()


@pytest.fixture(scope="session", name="generator")
def fixture_generator(translator):
    compiler = IdentityPlaquetteCompiler
    return FixedBoundaryConventionGenerator(translator, compiler)


def test_get_bulk_rpng_descriptions(generator):
    result = generator.get_bulk_rpng_descriptions(is_reversed=True)
    assert Basis.X in result
    # print(pprint.pprint(result,))


def test_get_3_body_rpng_descriptions(generator):
    generator.get_3_body_rpng_descriptions(basis=Basis.X, is_reversed=False)


def test_get_2_body_rpng_descriptions(generator):
    generator.get_2_body_rpng_descriptions(is_reversed=True)


# def test_get_extended_plaquettes(generator):
#   result = generator.get_extended_plaquettes()
