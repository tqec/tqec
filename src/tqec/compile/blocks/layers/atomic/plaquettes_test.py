import pytest

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates._testing import FixedTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


def test_creation() -> None:
    template = FixedTemplate([[1]])
    large_template = FixedTemplate([[1 for _ in range(10)] for _ in range(10)])
    plaquettes = Plaquettes(
        FrozenDefaultDict({}, default_factory=empty_square_plaquette)
    )
    PlaquetteLayer(template, plaquettes)
    PlaquetteLayer(
        large_template,
        plaquettes,
        spatial_borders_removed=frozenset([SpatialBlockBorder.X_NEGATIVE]),
    )
    PlaquetteLayer(
        large_template,
        plaquettes,
        spatial_borders_removed=frozenset(SpatialBlockBorder),
    )

    with pytest.raises(TQECException):
        PlaquetteLayer(
            template,
            plaquettes,
            spatial_borders_removed=frozenset([SpatialBlockBorder.X_NEGATIVE]),
        )


def test_scalable_shape() -> None:
    template = FixedTemplate([[1]])
    large_template = FixedTemplate([[1 for _ in range(10)] for _ in range(10)])
    plaquettes = Plaquettes(
        FrozenDefaultDict({}, default_factory=empty_square_plaquette)
    )
    single_plaquette_shape = PhysicalQubitScalable2D(
        LinearFunction(0, 3), LinearFunction(0, 3)
    )
    assert PlaquetteLayer(template, plaquettes).scalable_shape == single_plaquette_shape
    assert PlaquetteLayer(
        large_template,
        plaquettes,
        spatial_borders_removed=frozenset([SpatialBlockBorder.X_NEGATIVE]),
    ).scalable_shape == PhysicalQubitScalable2D(
        LinearFunction(0, 19), LinearFunction(0, 21)
    )
    assert PlaquetteLayer(
        large_template,
        plaquettes,
        spatial_borders_removed=frozenset(SpatialBlockBorder),
    ).scalable_shape == PhysicalQubitScalable2D(
        LinearFunction(0, 17), LinearFunction(0, 17)
    )
