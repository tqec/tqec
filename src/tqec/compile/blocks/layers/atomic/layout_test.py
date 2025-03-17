from typing import Final

import pytest

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

LOGICAL_QUBIT_SIDE: Final = LinearFunction(4, 5)
LOGICAL_QUBIT_SHAPE: Final = PhysicalQubitScalable2D(
    LOGICAL_QUBIT_SIDE, LOGICAL_QUBIT_SIDE
)


@pytest.fixture(name="plaquette_layer")
def plaquette_layer_fixture() -> PlaquetteLayer:
    template = QubitTemplate()
    plaquettes = Plaquettes(
        FrozenDefaultDict({}, default_factory=empty_square_plaquette)
    )
    return PlaquetteLayer(template, plaquettes)


def test_creation(plaquette_layer: PlaquetteLayer) -> None:
    with pytest.raises(TQECException, match=".*should have at least one layer.$"):
        LayoutLayer({}, LOGICAL_QUBIT_SHAPE)
    pos = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    LayoutLayer({pos: plaquette_layer}, LOGICAL_QUBIT_SHAPE)
    pos2 = LayoutPosition2D.from_block_position(BlockPosition2D(-93485, 12))
    LayoutLayer({pos2: plaquette_layer}, LOGICAL_QUBIT_SHAPE)
    LayoutLayer({pos: plaquette_layer, pos2: plaquette_layer}, LOGICAL_QUBIT_SHAPE)


def test_bounds(plaquette_layer: PlaquetteLayer) -> None:
    with pytest.raises(TQECException, match=".*should have at least one layer.$"):
        LayoutLayer({}, LOGICAL_QUBIT_SHAPE)
    pos1 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    pos2 = LayoutPosition2D.from_block_position(BlockPosition2D(-93485, 12))
    layer = LayoutLayer({pos1: plaquette_layer}, LOGICAL_QUBIT_SHAPE)
    assert layer.bounds == (BlockPosition2D(0, 0), BlockPosition2D(0, 0))
    layer = LayoutLayer(
        {pos1: plaquette_layer, pos2: plaquette_layer}, LOGICAL_QUBIT_SHAPE
    )
    assert layer.bounds == (BlockPosition2D(-93485, 0), BlockPosition2D(0, 12))


def test_scalable_timesteps(plaquette_layer: PlaquetteLayer) -> None:
    with pytest.raises(TQECException, match=".*should have at least one layer.$"):
        LayoutLayer({}, LOGICAL_QUBIT_SHAPE)
    pos1 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    layer = LayoutLayer({pos1: plaquette_layer}, LOGICAL_QUBIT_SHAPE)
    assert layer.scalable_timesteps == LinearFunction(0, 1)


def test_scalable_shape(plaquette_layer: PlaquetteLayer) -> None:
    with pytest.raises(TQECException, match=".*should have at least one layer.$"):
        LayoutLayer({}, LOGICAL_QUBIT_SHAPE)
    pos1 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    pos2 = LayoutPosition2D.from_block_position(BlockPosition2D(-1, 12))
    layer = LayoutLayer({pos1: plaquette_layer}, LOGICAL_QUBIT_SHAPE)
    assert layer.scalable_shape == LOGICAL_QUBIT_SHAPE
    layer = LayoutLayer(
        {pos1: plaquette_layer, pos2: plaquette_layer}, LOGICAL_QUBIT_SHAPE
    )
    assert layer.scalable_shape == PhysicalQubitScalable2D(
        2 * LOGICAL_QUBIT_SIDE - 1, 13 * (LOGICAL_QUBIT_SIDE - 1) + 1
    )
