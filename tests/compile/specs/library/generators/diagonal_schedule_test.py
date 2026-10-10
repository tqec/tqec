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
    assert generator.get_bulk_rpng_descriptions(is_reversed=False) == {
        Basis.X: {
            Orientation.VERTICAL: RPNGDescription.from_string("-x7- -x5- -x4- -x6-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-x7- -x5- -x4- -x6-"),
        },
        Basis.Z: {
            Orientation.VERTICAL: RPNGDescription.from_string("-z1- -z3- -z4- -z2-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-z1- -z3- -z4- -z2-"),
        },
    }


def test_fixed_bulk_generator_uses_reversed_diagonal_bulk_orders() -> None:
    generator = _make_generator()
    assert generator.get_bulk_rpng_descriptions(is_reversed=True) == {
        Basis.X: {
            Orientation.VERTICAL: RPNGDescription.from_string("-x6- -x4- -x5- -x7-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-x6- -x4- -x5- -x7-"),
        },
        Basis.Z: {
            Orientation.VERTICAL: RPNGDescription.from_string("-z2- -z4- -z3- -z1-"),
            Orientation.HORIZONTAL: RPNGDescription.from_string("-z2- -z4- -z3- -z1-"),
        },
    }


def test_fixed_bulk_generator_derives_diagonal_boundary_descriptions() -> None:
    generator = _make_generator()

    assert generator.get_2_body_rpng_descriptions(is_reversed=False) == {
        Basis.X: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-x7- -x5- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -x5- ---- -x6-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -x4- -x6-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-x7- ---- -x4- ----"),
        },
        Basis.Z: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-z1- -z3- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -z3- ---- -z2-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -z4- -z2-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-z1- ---- -z4- ----"),
        },
    }


def test_fixed_bulk_generator_derives_reversed_diagonal_boundary_descriptions() -> None:
    generator = _make_generator()

    assert generator.get_2_body_rpng_descriptions(is_reversed=True) == {
        Basis.X: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-x6- -x4- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -x4- ---- -x7-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -x5- -x7-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-x6- ---- -x5- ----"),
        },
        Basis.Z: {
            PlaquetteOrientation.DOWN: RPNGDescription.from_string("-z2- -z4- ---- ----"),
            PlaquetteOrientation.LEFT: RPNGDescription.from_string("---- -z4- ---- -z1-"),
            PlaquetteOrientation.UP: RPNGDescription.from_string("---- ---- -z3- -z1-"),
            PlaquetteOrientation.RIGHT: RPNGDescription.from_string("-z2- ---- -z3- ----"),
        },
    }
