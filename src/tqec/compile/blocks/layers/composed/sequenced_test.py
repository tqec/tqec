import pytest
import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitSpatialCubeTemplate, QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="plaquette_layer")
def plaquette_layer_fixture() -> PlaquetteLayer:
    return PlaquetteLayer(
        QubitTemplate(),
        Plaquettes(FrozenDefaultDict({}, default_factory=empty_square_plaquette)),
    )


@pytest.fixture(name="plaquette_layer2")
def plaquette_layer2_fixture() -> PlaquetteLayer:
    return PlaquetteLayer(
        QubitSpatialCubeTemplate(),
        Plaquettes(FrozenDefaultDict({}, default_factory=empty_square_plaquette)),
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


def test_creation(
    plaquette_layer: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
    raw_circuit_fixed_size_layer: RawCircuitLayer,
) -> None:
    # Invalid sequences due to duration <= 1
    err_regex = ".*expected to have multiple layers in sequence.*"
    for seq in ([], [plaquette_layer], [raw_circuit_layer]):
        with pytest.raises(TQECException, match=err_regex):
            SequencedLayers(seq)
    # Invalid sequence due to different shapes
    with pytest.raises(TQECException, match="Found at least two different shapes.*"):
        SequencedLayers(
            [plaquette_layer, raw_circuit_layer, raw_circuit_fixed_size_layer]
        )

    SequencedLayers([plaquette_layer for _ in range(10)])
    SequencedLayers(
        [
            plaquette_layer,
            RepeatedLayer(raw_circuit_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    )
    SequencedLayers(
        [
            SequencedLayers([plaquette_layer, raw_circuit_layer, plaquette_layer]),
            RepeatedLayer(raw_circuit_layer, LinearFunction(2, 0)),
        ]
    )


def test_schedule(plaquette_layer: PlaquetteLayer) -> None:
    assert SequencedLayers([plaquette_layer for _ in range(10)]).schedule == tuple(
        LinearFunction(0, 1) for _ in range(10)
    )
    assert SequencedLayers(
        [
            plaquette_layer,
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    ).schedule == (LinearFunction(0, 1), LinearFunction(2, 0), LinearFunction(0, 1))
    assert SequencedLayers(
        [
            SequencedLayers([plaquette_layer, plaquette_layer, plaquette_layer]),
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
        ]
    ).schedule == (LinearFunction(0, 3), LinearFunction(2, 0))


def test_scalable_timesteps(plaquette_layer: PlaquetteLayer) -> None:
    assert SequencedLayers(
        [plaquette_layer for _ in range(10)]
    ).scalable_timesteps == LinearFunction(0, 10)
    assert SequencedLayers(
        [
            plaquette_layer,
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    ).scalable_timesteps == LinearFunction(2, 2)
    assert SequencedLayers(
        [
            SequencedLayers([plaquette_layer, plaquette_layer, plaquette_layer]),
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
        ]
    ).scalable_timesteps == LinearFunction(2, 3)


@pytest.mark.parametrize("borders", [(border,) for border in SpatialBlockBorder])
def test_with_spatial_borders_trimmed(
    borders: tuple[SpatialBlockBorder, ...], plaquette_layer: PlaquetteLayer
) -> None:
    layer = SequencedLayers([plaquette_layer for _ in range(5)])
    trimmed_layer = layer.with_spatial_borders_trimmed(borders)
    trimmed_internal_layer = plaquette_layer.with_spatial_borders_trimmed(borders)
    assert all(
        internal_layer == trimmed_internal_layer
        for internal_layer in trimmed_layer.layer_sequence
    )


def test_with_temporal_borders_replaced_none(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    layer = SequencedLayers([plaquette_layer, plaquette_layer2, raw_circuit_layer])
    assert layer.with_temporal_borders_replaced({}) == layer
    assert layer.with_temporal_borders_replaced(
        {TemporalBlockBorder.Z_NEGATIVE: None}
    ) == SequencedLayers([plaquette_layer2, raw_circuit_layer])
    assert layer.with_temporal_borders_replaced(
        {TemporalBlockBorder.Z_POSITIVE: None}
    ) == SequencedLayers([plaquette_layer, plaquette_layer2])
    assert (
        layer.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: None, TemporalBlockBorder.Z_POSITIVE: None}
        )
        == plaquette_layer2
    )
    # Shorter to cover one edge-case:
    assert (
        SequencedLayers(
            [plaquette_layer, raw_circuit_layer]
        ).with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: None, TemporalBlockBorder.Z_POSITIVE: None}
        )
        is None
    )


def test_with_temporal_borders_replaced(
    plaquette_layer: PlaquetteLayer,
    plaquette_layer2: PlaquetteLayer,
    raw_circuit_layer: RawCircuitLayer,
) -> None:
    layer = SequencedLayers([plaquette_layer, plaquette_layer2, raw_circuit_layer])

    assert layer.with_temporal_borders_replaced({}) == layer
    for replacement in [plaquette_layer, plaquette_layer2, raw_circuit_layer]:
        assert layer.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_NEGATIVE: replacement}
        ) == SequencedLayers([replacement, plaquette_layer2, raw_circuit_layer])
        assert layer.with_temporal_borders_replaced(
            {TemporalBlockBorder.Z_POSITIVE: replacement}
        ) == SequencedLayers([plaquette_layer, plaquette_layer2, replacement])
        assert layer.with_temporal_borders_replaced(
            {
                TemporalBlockBorder.Z_NEGATIVE: replacement,
                TemporalBlockBorder.Z_POSITIVE: replacement,
            }
        ) == SequencedLayers([replacement, plaquette_layer2, replacement])
    assert layer.with_temporal_borders_replaced(
        {
            TemporalBlockBorder.Z_NEGATIVE: None,
            TemporalBlockBorder.Z_POSITIVE: plaquette_layer2,
        }
    ) == SequencedLayers([plaquette_layer2, plaquette_layer2])


def test_to_sequenced_layer_with_schedule(plaquette_layer: PlaquetteLayer) -> None:
    layer = SequencedLayers(
        [RepeatedLayer(plaquette_layer, LinearFunction(2, 0)), plaquette_layer]
    )
    assert (
        layer.to_sequenced_layer_with_schedule(
            (LinearFunction(2, 0), LinearFunction(0, 1))
        )
        == layer
    )
    err_regex = (
        "^.*The provided schedule has a duration of .* but the instance "
        "to transform has a duration of .*$"
    )
    with pytest.raises(TQECException, match=err_regex):
        layer.to_sequenced_layer_with_schedule(
            (LinearFunction(0, 1), LinearFunction(1, 0))
        )
    with pytest.raises(NotImplementedError):
        layer.to_sequenced_layer_with_schedule(
            (LinearFunction(0, 1), LinearFunction(2, 0))
        )
