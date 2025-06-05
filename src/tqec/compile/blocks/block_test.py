import pytest
import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.block import Block, merge_parallel_block_layers
from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitSpatialCubeTemplate, QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="plaquette_layer")
def plaquette_layer_fixture() -> PlaquetteLayer:
    return PlaquetteLayer(
        QubitTemplate(),
        Plaquettes(FrozenDefaultDict({}, default_value=empty_square_plaquette())),
    )


@pytest.fixture(name="plaquette_layer2")
def plaquette_layer2_fixture() -> PlaquetteLayer:
    return PlaquetteLayer(
        QubitSpatialCubeTemplate(),
        Plaquettes(FrozenDefaultDict({}, default_value=empty_square_plaquette())),
    )


@pytest.fixture(name="raw_circuit_layer")
def raw_circuit_layer_fixture() -> RawCircuitLayer:
    return RawCircuitLayer(
        lambda k: ScheduledCircuit.from_circuit(stim.Circuit()),
        PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5)),
    )


@pytest.fixture(name="raw_circuit_fixed_size_layer")
def raw_circuit_fixed_size_layer_fixture() -> RawCircuitLayer:
    return RawCircuitLayer(
        lambda k: ScheduledCircuit.from_circuit(stim.Circuit()),
        PhysicalQubitScalable2D(LinearFunction(0, 1), LinearFunction(0, 1)),
    )


@pytest.fixture(name="base_layers")
def base_layers_fixture() -> list[BaseLayer]:
    return [
        PlaquetteLayer(
            QubitTemplate(),
            Plaquettes(FrozenDefaultDict({}, default_value=empty_square_plaquette())),
        ),
        PlaquetteLayer(
            QubitSpatialCubeTemplate(),
            Plaquettes(FrozenDefaultDict({}, default_value=empty_square_plaquette())),
        ),
        RawCircuitLayer(
            lambda k: ScheduledCircuit.from_circuit(stim.Circuit()),
            PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5)),
        ),
    ]


@pytest.fixture(name="logical_qubit_shape")
def logical_qubit_shape_fixture() -> PhysicalQubitScalable2D:
    return PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5))


def test_creation(plaquette_layer: PlaquetteLayer, raw_circuit_layer: RawCircuitLayer) -> None:
    # Invalid sequences due to duration < 1
    err_regex = ".*expected to have at least one layer.*"
    with pytest.raises(TQECException, match=err_regex):
        Block([])

    Block([plaquette_layer for _ in range(10)])
    Block(
        [
            plaquette_layer,
            RepeatedLayer(raw_circuit_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    )
    Block(
        [
            SequencedLayers([plaquette_layer, raw_circuit_layer, plaquette_layer]),
            RepeatedLayer(raw_circuit_layer, LinearFunction(2, 0)),
        ]
    )


@pytest.mark.parametrize("borders", [(border,) for border in SpatialBlockBorder])
def test_with_spatial_borders_trimmed(
    borders: tuple[SpatialBlockBorder, ...], plaquette_layer: PlaquetteLayer
) -> None:
    block = Block([plaquette_layer for _ in range(5)])
    trimmed_block = block.with_spatial_borders_trimmed(borders)
    trimmed_internal_layer = plaquette_layer.with_spatial_borders_trimmed(borders)
    assert all(
        internal_layer == trimmed_internal_layer for internal_layer in trimmed_block.layer_sequence
    )


def test_with_temporal_borders_replaced_none(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    block = Block([plaquette_layer, plaquette_layer2, raw_circuit_layer])
    assert block.with_temporal_borders_replaced({}) == block
    assert block.with_temporal_borders_replaced({TemporalBlockBorder.Z_NEGATIVE: None}) == Block(
        [plaquette_layer2, raw_circuit_layer]
    )
    assert block.with_temporal_borders_replaced({TemporalBlockBorder.Z_POSITIVE: None}) == Block(
        [plaquette_layer, plaquette_layer2]
    )
    assert block.with_temporal_borders_replaced(
        {TemporalBlockBorder.Z_NEGATIVE: None, TemporalBlockBorder.Z_POSITIVE: None}
    ) == Block([plaquette_layer2])
    # Shorter to cover one edge-case:
    assert (
        Block([plaquette_layer, raw_circuit_layer]).with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: None, TemporalBlockBorder.Z_POSITIVE: None}
        )
        is None
    )


def test_with_temporal_borders_replaced(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    block = Block([plaquette_layer, plaquette_layer2, raw_circuit_layer])

    assert block.with_temporal_borders_replaced({}) == block
    for replacement in [plaquette_layer, plaquette_layer2, raw_circuit_layer]:
        assert block.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: replacement}
        ) == Block([replacement, plaquette_layer2, raw_circuit_layer])
        assert block.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_POSITIVE: replacement}
        ) == Block([plaquette_layer, plaquette_layer2, replacement])
        assert block.with_temporal_borders_replaced(
            {
                TemporalBlockBorder.Z_NEGATIVE: replacement,
                TemporalBlockBorder.Z_POSITIVE: replacement,
            }
        ) == Block([replacement, plaquette_layer2, replacement])
    assert block.with_temporal_borders_replaced(
        {
            TemporalBlockBorder.Z_NEGATIVE: None,
            TemporalBlockBorder.Z_POSITIVE: plaquette_layer2,
        }
    ) == Block([plaquette_layer2, plaquette_layer2])


def test_get_temporal_border(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    block = Block([plaquette_layer, raw_circuit_layer, plaquette_layer2])
    assert block.get_temporal_border(TemporalBlockBorder.Z_NEGATIVE) == plaquette_layer
    assert block.get_temporal_border(TemporalBlockBorder.Z_POSITIVE) == plaquette_layer2

    block = Block(
        [
            RepeatedLayer(plaquette_layer, LinearFunction(0, 2)),
            plaquette_layer2,
            raw_circuit_layer,
        ]
    )
    with pytest.raises(
        TQECException,
        match=r"^Expected to recover a temporal \*\*border\*\* \(i.e. an atomic layer\) "
        "but got an instance of RepeatedLayer instead.$",
    ):
        block.get_temporal_border(TemporalBlockBorder.Z_NEGATIVE)


def test_dimensions(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    assert Block([plaquette_layer, raw_circuit_layer, plaquette_layer2]).dimensions == (
        LinearFunction(4, 5),
        LinearFunction(4, 5),
        LinearFunction(0, 3),
    )
    assert Block(
        [
            RepeatedLayer(plaquette_layer, LinearFunction(56, 2)),
            plaquette_layer2,
            raw_circuit_layer,
        ]
    ).dimensions == (
        LinearFunction(4, 5),
        LinearFunction(4, 5),
        LinearFunction(56, 4),
    )


def test_is_cube(plaquette_layer: PlaquetteLayer) -> None:
    assert Block(
        [
            plaquette_layer,
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    ).is_cube
    assert not Block([plaquette_layer, plaquette_layer]).is_cube


def test_is_pipe(plaquette_layer: PlaquetteLayer) -> None:
    assert not Block(
        [
            plaquette_layer,
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    ).is_pipe
    assert Block([plaquette_layer, plaquette_layer]).is_pipe


def test_is_temporal_pipe(plaquette_layer: PlaquetteLayer) -> None:
    assert Block([plaquette_layer, plaquette_layer]).is_temporal_pipe


def test_merge_parallel_block_layers(
    base_layers: list[BaseLayer], logical_qubit_shape: PhysicalQubitScalable2D
) -> None:
    plaquette_layer, plaquette_layer2, raw_layer = base_layers
    b00 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 0))
    b01 = LayoutPosition2D.from_block_position(BlockPosition2D(0, 1))
    merged_layers = merge_parallel_block_layers(
        {
            b00: Block(
                [
                    plaquette_layer,
                    RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
                    plaquette_layer,
                ]
            ),
            b01: Block(
                [
                    plaquette_layer,
                    RepeatedLayer(
                        SequencedLayers([plaquette_layer2, raw_layer]),
                        LinearFunction(1, 0),
                    ),
                    plaquette_layer2,
                ]
            ),
        },
        logical_qubit_shape,
    )
    assert merged_layers == [
        LayoutLayer({b00: plaquette_layer, b01: plaquette_layer}, logical_qubit_shape),
        RepeatedLayer(
            SequencedLayers(
                [
                    LayoutLayer(
                        {b00: plaquette_layer, b01: plaquette_layer2},
                        logical_qubit_shape,
                    ),
                    LayoutLayer({b00: plaquette_layer, b01: raw_layer}, logical_qubit_shape),
                ]
            ),
            LinearFunction(1, 0),
        ),
        LayoutLayer({b00: plaquette_layer, b01: plaquette_layer2}, logical_qubit_shape),
    ]
