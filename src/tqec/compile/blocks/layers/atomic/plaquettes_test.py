import itertools

import pytest

from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates._testing import FixedTemplate
from tqec.templates.qubit import QubitTemplate
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

_TRANSLATOR = DefaultRPNGTranslator()
_EMPTY_PLAQUETTE = _TRANSLATOR.translate(RPNGDescription.empty())


def test_creation() -> None:
    template = FixedTemplate([[1]])
    large_template = FixedTemplate([[1 for _ in range(10)] for _ in range(10)])
    plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    PlaquetteLayer(template, plaquettes)
    PlaquetteLayer(
        large_template,
        plaquettes,
        trimmed_spatial_borders=frozenset([SpatialBlockBorder.X_NEGATIVE]),
    )
    PlaquetteLayer(
        large_template,
        plaquettes,
        trimmed_spatial_borders=frozenset(SpatialBlockBorder),
    )

    with pytest.raises(TQECError):
        PlaquetteLayer(
            template,
            plaquettes,
            trimmed_spatial_borders=frozenset([SpatialBlockBorder.X_NEGATIVE]),
        )


def test_scalable_shape() -> None:
    template = FixedTemplate([[1]])
    large_template = FixedTemplate([[1 for _ in range(10)] for _ in range(10)])
    plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    single_plaquette_shape = PhysicalQubitScalable2D(LinearFunction(0, 3), LinearFunction(0, 3))
    assert PlaquetteLayer(template, plaquettes).scalable_shape == single_plaquette_shape
    assert PlaquetteLayer(
        large_template,
        plaquettes,
        trimmed_spatial_borders=frozenset([SpatialBlockBorder.X_NEGATIVE]),
    ).scalable_shape == PhysicalQubitScalable2D(LinearFunction(0, 19), LinearFunction(0, 21))
    assert PlaquetteLayer(
        large_template,
        plaquettes,
        trimmed_spatial_borders=frozenset(SpatialBlockBorder),
    ).scalable_shape == PhysicalQubitScalable2D(LinearFunction(0, 17), LinearFunction(0, 17))


@pytest.mark.parametrize("borders", [(border,) for border in SpatialBlockBorder])
def test_with_spatial_borders_trimmed(borders: tuple[SpatialBlockBorder, ...]) -> None:
    template = QubitTemplate()
    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {i + 1: _EMPTY_PLAQUETTE for i in range(template.expected_plaquettes_number)},
            default_value=_EMPTY_PLAQUETTE,
        )
    )
    layer = PlaquetteLayer(template, plaquettes)
    all_indices = frozenset(plaquettes.collection.keys())
    expected_plaquette_indices = all_indices - frozenset(
        itertools.chain.from_iterable(
            frozenset(template.get_border_indices(border.to_template_border()))
            for border in borders
        )
    )
    assert (
        frozenset(layer.with_spatial_borders_trimmed(borders).plaquettes.collection.keys())
        == expected_plaquette_indices
    )


def test_with_temporal_borders_replaced_none() -> None:
    template = FixedTemplate([[1]])
    plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    layer = PlaquetteLayer(template, plaquettes)
    assert layer.with_temporal_borders_replaced({}) == layer
    assert layer.with_temporal_borders_replaced({TemporalBlockBorder.Z_NEGATIVE: None}) is None
    assert layer.with_temporal_borders_replaced({TemporalBlockBorder.Z_POSITIVE: None}) is None
    assert (
        layer.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: None, TemporalBlockBorder.Z_POSITIVE: None}
        )
        is None
    )


def test_with_temporal_borders_replaced() -> None:
    template = FixedTemplate([[1]])
    plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    layer = PlaquetteLayer(template, plaquettes)
    replacement_template = FixedTemplate([[2]])
    replacement_plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    replacement_layer = PlaquetteLayer(replacement_template, replacement_plaquettes)

    assert layer.with_temporal_borders_replaced({}) == layer
    for replacement in [None, layer, replacement_layer]:
        assert (
            layer.with_temporal_borders_replaced({TemporalBlockBorder.Z_NEGATIVE: replacement})
            == replacement
        )
    with pytest.raises(TQECError):
        layer.with_temporal_borders_replaced(
            {
                TemporalBlockBorder.Z_NEGATIVE: None,
                TemporalBlockBorder.Z_POSITIVE: replacement_layer,
            }
        )


def test_scalable_num_moments() -> None:
    template = FixedTemplate([[1]])
    plaquettes = Plaquettes(FrozenDefaultDict({}, default_value=_EMPTY_PLAQUETTE))
    layer = PlaquetteLayer(template, plaquettes)
    assert layer.scalable_num_moments == LinearFunction(0, 0)

    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {1: _TRANSLATOR.translate(RPNGDescription.from_string("-x1- -x2- -x3- -x4-"))},
            default_value=_EMPTY_PLAQUETTE,
        )
    )
    layer = PlaquetteLayer(template, plaquettes)
    # Note: even if there is no measurement in the plaquette, the measurement moment is
    # still present, and so is accounted for. That is an implementation detail of the
    # translator and may lead to inaccurate results.
    assert layer.scalable_num_moments == LinearFunction(0, MEASUREMENT_SCHEDULE + 1)

    plaquettes = Plaquettes(
        FrozenDefaultDict(
            {1: _TRANSLATOR.translate(RPNGDescription.from_string("-x1z -x2z -x3z -x4z"))},
            default_value=_EMPTY_PLAQUETTE,
        )
    )
    print(plaquettes[1].circuit.get_circuit())
    layer = PlaquetteLayer(template, plaquettes)
    assert layer.scalable_num_moments == LinearFunction(0, MEASUREMENT_SCHEDULE + 1)
