import pytest
import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.layers.merge import (
    _merge_base_layers,
    _merge_repeated_layers,
    _merge_sequenced_layers,
)
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitSpatialCubeTemplate, QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="base_layers")
def base_layers_fixture() -> list[BaseLayer]:
    return [
        PlaquetteLayer(
            QubitTemplate(),
            Plaquettes(FrozenDefaultDict({}, default_factory=empty_square_plaquette)),
        ),
        PlaquetteLayer(
            QubitSpatialCubeTemplate(),
            Plaquettes(FrozenDefaultDict({}, default_factory=empty_square_plaquette)),
        ),
        RawCircuitLayer(
            lambda k: ScheduledCircuit.from_circuit(stim.Circuit()),
            PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5)),
        ),
    ]


@pytest.fixture(name="logical_qubit_shape")
def logical_qubit_shape_fixture() -> PhysicalQubitScalable2D:
    return PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


def test_merge_base_layers(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    layout: dict[LayoutPosition2D, BaseLayer] = {
        LayoutPosition2D.from_block_position(BlockPosition2D(i, i)): layer
        for i, layer in enumerate(base_layers)
    }
    merged_layer = _merge_base_layers(layout, logical_qubit_shape)
    assert isinstance(merged_layer, LayoutLayer)
    assert merged_layer.layers == layout
    assert merged_layer.element_shape == logical_qubit_shape


def test_merge_repeated_layers(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    b11 = LayoutPosition2D.from_block_position(BlockPosition2D(1, 1))
    merged_layer = _merge_repeated_layers(
        {
            b00: RepeatedLayer(plaquette_layer, LinearFunction(2, 2)),
            b01: RepeatedLayer(plaquette_layer2, LinearFunction(2, 2)),
            b11: RepeatedLayer(raw_layer, LinearFunction(2, 2)),
        },
        logical_qubit_shape,
    )
    assert isinstance(merged_layer, RepeatedLayer)
    assert merged_layer.scalable_timesteps == LinearFunction(2, 2)
    assert merged_layer.scalable_shape == PhysicalQubitScalable2D(
        2 * logical_qubit_shape.x - 1, 2 * logical_qubit_shape.y - 1
    )
    assert merged_layer.repetitions == LinearFunction(2, 2)
    assert isinstance(merged_layer.internal_layer, LayoutLayer)
    assert merged_layer.internal_layer.element_shape == logical_qubit_shape
    assert merged_layer.internal_layer.layers == {
        b00: plaquette_layer,
        b01: plaquette_layer2,
        b11: raw_layer,
    }


def test_merge_repeated_layers_different_inner_durations(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    merged_layer = _merge_repeated_layers(
        {
            b00: RepeatedLayer(plaquette_layer, LinearFunction(2, 2)),
            b01: RepeatedLayer(
                SequencedLayers([plaquette_layer2, raw_layer]), LinearFunction(1, 1)
            ),
        },
        logical_qubit_shape,
    )
    assert isinstance(merged_layer, RepeatedLayer)
    assert merged_layer.scalable_timesteps == LinearFunction(2, 2)
    assert merged_layer.scalable_shape == PhysicalQubitScalable2D(
        logical_qubit_shape.x, 2 * logical_qubit_shape.y - 1
    )
    assert merged_layer.repetitions == LinearFunction(1, 1)
    assert isinstance(merged_layer.internal_layer, SequencedLayers)
    assert merged_layer.internal_layer.scalable_timesteps == LinearFunction(0, 2)
    assert merged_layer.internal_layer.layer_sequence == [
        LayoutLayer({b00: plaquette_layer, b01: plaquette_layer2}, logical_qubit_shape),
        LayoutLayer({b00: plaquette_layer, b01: raw_layer}, logical_qubit_shape),
    ]


def test_merge_repeated_layers_wrong_duration(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, _ = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    with pytest.raises(
        TQECException,
        match=".*Cannot merge RepeatedLayer instances that have different lengths..*",
    ):
        _merge_repeated_layers(
            {
                b00: RepeatedLayer(plaquette_layer, LinearFunction(2, 2)),
                b01: RepeatedLayer(plaquette_layer2, LinearFunction(2, 0)),
            },
            logical_qubit_shape,
        )


def test_merge_sequenced_layers(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    b11 = LayoutPosition2D.from_block_position(BlockPosition2D(1, 1))
    merged_layer = _merge_sequenced_layers(
        {
            b00: SequencedLayers([plaquette_layer, plaquette_layer2]),
            b01: SequencedLayers([plaquette_layer2, raw_layer]),
            b11: SequencedLayers([raw_layer, plaquette_layer]),
        },
        logical_qubit_shape,
    )
    assert isinstance(merged_layer, SequencedLayers)
    assert merged_layer.scalable_timesteps == LinearFunction(0, 2)
    assert merged_layer.scalable_shape == PhysicalQubitScalable2D(
        2 * logical_qubit_shape.x - 1, 2 * logical_qubit_shape.y - 1
    )
    assert merged_layer.layer_sequence == [
        LayoutLayer(
            {b00: plaquette_layer, b01: plaquette_layer2, b11: raw_layer},
            logical_qubit_shape,
        ),
        LayoutLayer(
            {b00: plaquette_layer2, b01: raw_layer, b11: plaquette_layer},
            logical_qubit_shape,
        ),
    ]


def test_merge_sequenced_layers_composed(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    b11 = LayoutPosition2D.from_block_position(BlockPosition2D(1, 1))
    merged_layer = _merge_sequenced_layers(
        {
            b00: SequencedLayers(
                [SequencedLayers([plaquette_layer, raw_layer]), plaquette_layer2]
            ),
            b01: SequencedLayers(
                [SequencedLayers([plaquette_layer2, plaquette_layer]), raw_layer]
            ),
            b11: SequencedLayers(
                [SequencedLayers([raw_layer, plaquette_layer2]), plaquette_layer]
            ),
        },
        logical_qubit_shape,
    )
    assert isinstance(merged_layer, SequencedLayers)
    assert merged_layer.scalable_timesteps == LinearFunction(0, 3)
    assert merged_layer.scalable_shape == PhysicalQubitScalable2D(
        2 * logical_qubit_shape.x - 1, 2 * logical_qubit_shape.y - 1
    )
    assert merged_layer.layer_sequence == [
        SequencedLayers(
            [
                LayoutLayer(
                    {b00: plaquette_layer, b01: plaquette_layer2, b11: raw_layer},
                    logical_qubit_shape,
                ),
                LayoutLayer(
                    {b00: raw_layer, b01: plaquette_layer, b11: plaquette_layer2},
                    logical_qubit_shape,
                ),
            ]
        ),
        LayoutLayer(
            {b00: plaquette_layer2, b01: raw_layer, b11: plaquette_layer},
            logical_qubit_shape,
        ),
    ]


def test_merge_sequenced_layers_composed_different_schedules(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    with pytest.raises(
        NotImplementedError,
        match=".*_merge_sequenced_layers only supports merging sequences that have layers with a matching temporal schedule..*",
    ):
        _merge_sequenced_layers(
            {
                b00: SequencedLayers(
                    [plaquette_layer2, SequencedLayers([plaquette_layer, raw_layer])]
                ),
                b01: SequencedLayers(
                    [SequencedLayers([plaquette_layer2, plaquette_layer]), raw_layer]
                ),
            },
            logical_qubit_shape,
        )
