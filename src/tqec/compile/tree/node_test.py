from typing import Final

import pytest

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.compile.tree.node import LayerNode, NodeWalker
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
        FrozenDefaultDict({}, default_value=empty_square_plaquette())
    )
    return PlaquetteLayer(template, plaquettes)


@pytest.fixture(name="layout_layer")
def layout_layer_fixture() -> LayoutLayer:
    template = QubitTemplate()
    plaquettes = Plaquettes(
        FrozenDefaultDict({}, default_value=empty_square_plaquette())
    )
    return LayoutLayer(
        {
            LayoutPosition2D.from_block_position(BlockPosition2D(x, y)): PlaquetteLayer(
                template, plaquettes
            )
            for x, y in [(0, 0), (1, 0)]
        },
        LOGICAL_QUBIT_SHAPE,
    )


def test_creation(plaquette_layer: PlaquetteLayer, layout_layer: LayoutLayer) -> None:
    LayerNode(layout_layer)
    LayerNode(RepeatedLayer(layout_layer, LinearFunction(2, 0)))
    LayerNode(SequencedLayers([layout_layer for _ in range(3)]))
    with pytest.raises(
        TQECException,
        match="The layer that is being repeated is not an instance of LayoutLayer or BaseComposedLayer.",
    ):
        LayerNode(RepeatedLayer(plaquette_layer, LinearFunction(2, 0)))
    with pytest.raises(
        TQECException,
        match="Found a leaf node that is not an instance of LayoutLayer..*",
    ):
        LayerNode(SequencedLayers([plaquette_layer for _ in range(4)]))


def test_is_leaf(layout_layer: LayoutLayer) -> None:
    assert LayerNode(layout_layer).is_leaf
    assert not LayerNode(RepeatedLayer(layout_layer, LinearFunction(2, 0))).is_leaf
    assert not LayerNode(SequencedLayers([layout_layer for _ in range(3)])).is_leaf


def test_is_repeated(layout_layer: LayoutLayer) -> None:
    assert not LayerNode(layout_layer).is_repeated
    assert LayerNode(RepeatedLayer(layout_layer, LinearFunction(2, 0))).is_repeated
    assert not LayerNode(SequencedLayers([layout_layer for _ in range(3)])).is_repeated


def test_walk_see_all_leaf_nodes(layout_layer: LayoutLayer) -> None:
    class LeavesCounter(NodeWalker):
        def __init__(self) -> None:
            super().__init__()
            self._counter = 0

        def visit_node(self, node: LayerNode) -> None:
            self._counter += node.is_leaf

    def count_leaves(node: LayerNode) -> int:
        counter = LeavesCounter()
        node.walk(counter)
        return counter._counter

    assert count_leaves(LayerNode(layout_layer)) == 1
    assert (
        count_leaves(LayerNode(RepeatedLayer(layout_layer, LinearFunction(2, 0)))) == 1
    )  # Because RepeatedLayer has only its repeated node as child.
    assert (
        count_leaves(LayerNode(SequencedLayers([layout_layer for _ in range(3)]))) == 3
    )
    assert (
        count_leaves(
            LayerNode(
                SequencedLayers(
                    [
                        SequencedLayers([layout_layer for _ in range(3)])
                        for _ in range(5)
                    ]
                )
            )
        )
        == 15
    )
