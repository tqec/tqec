from tqec.compile.specs.library.generators.diagonal_schedule import DiagonalScheduleGenerator
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng import RPNGDescription
from tqec.utils.enums import Basis, Orientation


def test_diagonal_schedule_generator_uses_paper_final_bulk_orders() -> None:
    generator = DiagonalScheduleGenerator()
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


def test_diagonal_schedule_generator_derives_boundary_descriptions_from_bulk_orders() -> None:
    generator = DiagonalScheduleGenerator()
    descriptions = generator.get_2_body_rpng_descriptions()

    assert descriptions[Basis.X][PlaquetteOrientation.DOWN] == RPNGDescription.from_string(
        "-x7- -x5- ---- ----"
    )
    assert descriptions[Basis.Z][PlaquetteOrientation.RIGHT] == RPNGDescription.from_string(
        "-z1- ---- -z4- ----"
    )
