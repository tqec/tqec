import pytest

from tqec.compile.specs.enums import PipeCubeArmConfig
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.schedules import (
    DEFAULT_SCHEDULE_FAMILY,
    DIAGONAL_SCHEDULE_FAMILY,
    PlaquetteScheduleFamily,
)
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis


def _make_generator(
    schedule_family: PlaquetteScheduleFamily = DEFAULT_SCHEDULE_FAMILY,
) -> FixedBulkConventionGenerator:
    return FixedBulkConventionGenerator(
        DefaultRPNGTranslator(schedule_family.measurement_schedule),
        IdentityPlaquetteCompiler,
        schedule_family,
    )


def _names(plaquettes) -> dict[int, str]:
    return {index: plaquette.name for index, plaquette in plaquettes.collection.items()}


def test_spatial_horizontal_hadamard_reuses_extended_stabiliser_plaquettes() -> None:
    """The Y-axis wrapper is exactly the extended-stabiliser Hadamard (no-arm config)."""
    generator = _make_generator()
    for top_left_is_z, spatial_boundary_basis, arms in (
        (True, Basis.Z, PipeCubeArmConfig.NRNR),
        (False, Basis.X, PipeCubeArmConfig.NLNL),
    ):
        assert _names(
            generator.get_spatial_horizontal_hadamard_plaquettes(top_left_is_z)
        ) == _names(
            generator.get_spatial_extended_stabiliser_hadamard_plqts(spatial_boundary_basis, arms)
        )


def test_spatial_horizontal_hadamard_flag_selects_the_boundary_semicircles() -> None:
    """``top_left_is_z_stabilizer`` only moves the boundary (semi-circle) plaquettes.

    The bulk extended stabilisers have the same basis in both branches: they are
    keyed by their position in the checkerboard, not by the wall basis.
    """
    generator = _make_generator()
    z_names = _names(generator.get_spatial_horizontal_hadamard_plaquettes(True))
    x_names = _names(generator.get_spatial_horizontal_hadamard_plaquettes(False))

    assert sorted(z_names) == [2, 4, 5, 6, 7, 8]
    assert sorted(x_names) == [1, 3, 5, 6, 7, 8]
    for index in (5, 6, 7, 8):
        assert z_names[index] == x_names[index]
    assert "_LZ_" in z_names[2]
    assert "_LX_" in z_names[4]
    assert "_LX_" in x_names[1]
    assert "_LZ_" in x_names[3]


def test_spatial_horizontal_hadamard_rejects_non_default_schedule_family() -> None:
    """The reused extended stabilisers have a fixed timing: other families cannot host them."""
    generator = _make_generator(DIAGONAL_SCHEDULE_FAMILY)
    with pytest.raises(NotImplementedError):
        generator.get_spatial_horizontal_hadamard_plaquettes(True)
    with pytest.raises(NotImplementedError):
        generator.get_spatial_horizontal_hadamard_plaquettes(False)
