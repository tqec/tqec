import pytest

from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.library.generators.fixed_boundary import FixedBoundaryConventionGenerator
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.utils import (
    get_reset_measurement_indices_for_spatial_arms,
)
from tqec.computation.cube import ZXCube
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.enums import Basis


@pytest.mark.parametrize("bottom", [False, True])
@pytest.mark.parametrize("top", [False, True])
@pytest.mark.parametrize("reset", [None, Basis.X])
@pytest.mark.parametrize("measurement", [None, Basis.Z])
def test_spatial_arm_reset_and_measurement_indices(bottom, top, reset, measurement):
    cube = CubeSpec(
        ZXCube.from_str("ZXZ"),
        has_bottom_temporal_pipe=bottom,
        has_top_temporal_pipe=top,
    )
    assert get_reset_measurement_indices_for_spatial_arms((1, 3), cube, reset, measurement) == (
        (0, 1, 2, 3) if reset is not None and not bottom else (1, 3),
        (0, 1, 2, 3) if measurement is not None and not top else (1, 3),
    )


def test_spatial_arm_indices_without_neighbor():
    assert get_reset_measurement_indices_for_spatial_arms((1, 3), None, Basis.X, Basis.Z) == (
        (1, 3),
        (1, 3),
    )


@pytest.mark.parametrize(
    "generator_type", [FixedBulkConventionGenerator, FixedBoundaryConventionGenerator]
)
@pytest.mark.parametrize("reset_indices", [(), (1, 3), (0, 1, 2, 3)])
@pytest.mark.parametrize("measured_indices", [(), (0, 2), (0, 1, 2, 3)])
def test_bulk_reset_and_measurement_indices_are_independent(
    generator_type, reset_indices, measured_indices
):
    generator = generator_type(DefaultRPNGTranslator(), IdentityPlaquetteCompiler)
    kwargs = {"is_reversed": False} if generator_type is FixedBoundaryConventionGenerator else {}
    descriptions = generator.get_bulk_rpng_descriptions(
        reset=Basis.X,
        measurement=Basis.Z,
        reset_indices=reset_indices,
        measured_indices=measured_indices,
        **kwargs,
    )
    for orientations in descriptions.values():
        for description in orientations.values():
            corners = str(description).split()
            assert tuple(i for i, corner in enumerate(corners) if corner[0] == "x") == reset_indices
            assert (
                tuple(i for i, corner in enumerate(corners) if corner[3] == "z") == measured_indices
            )


@pytest.mark.parametrize(
    "generator_type", [FixedBulkConventionGenerator, FixedBoundaryConventionGenerator]
)
def test_bulk_measurement_indices_default_independently(generator_type):
    generator = generator_type(DefaultRPNGTranslator(), IdentityPlaquetteCompiler)
    kwargs = {"is_reversed": False} if generator_type is FixedBoundaryConventionGenerator else {}
    descriptions = generator.get_bulk_rpng_descriptions(
        reset=Basis.X, measurement=Basis.Z, reset_indices=(1, 3), **kwargs
    )
    for orientations in descriptions.values():
        for description in orientations.values():
            assert all(corner[3] == "z" for corner in str(description).split())
