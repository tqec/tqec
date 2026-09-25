from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis, Orientation


def _make_generator() -> FixedBulkConventionGenerator:
    return FixedBulkConventionGenerator(
        DefaultRPNGTranslator(DIAGONAL_SCHEDULE_FAMILY.measurement_schedule),
        IdentityPlaquetteCompiler,
        DIAGONAL_SCHEDULE_FAMILY,
    )


def test_fixed_bulk_generator_uses_diagonal_bulk_orders() -> None:
    generator = _make_generator()
    descriptions = generator.get_bulk_rpng_descriptions()

    assert descriptions[Basis.X][Orientation.VERTICAL] == RPNGDescription.from_string(
        "-x7- -x5- -x4- -x6-"
    )
    assert descriptions[Basis.X][Orientation.HORIZONTAL] == RPNGDescription.from_string(
        "-x7- -x5- -x4- -x6-"
    )
    assert descriptions[Basis.Z][Orientation.VERTICAL] == RPNGDescription.from_string(
        "-z1- -z3- -z4- -z2-"
    )
    assert descriptions[Basis.Z][Orientation.HORIZONTAL] == RPNGDescription.from_string(
        "-z1- -z3- -z4- -z2-"
    )


def test_fixed_bulk_generator_derives_diagonal_boundary_descriptions() -> None:
    generator = _make_generator()
    descriptions = generator.get_2_body_rpng_descriptions()

    assert descriptions[Basis.X][PlaquetteOrientation.DOWN] == RPNGDescription.from_string(
        "-x7- -x5- ---- ----"
    )
    assert descriptions[Basis.Z][PlaquetteOrientation.RIGHT] == RPNGDescription.from_string(
        "-z1- ---- -z4- ----"
    )
