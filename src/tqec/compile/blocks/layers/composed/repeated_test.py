import itertools

import pytest
import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.plaquette.library.empty import empty_square_plaquette
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@pytest.fixture(name="plaquette_layer")
def plaquette_layer_fixture() -> PlaquetteLayer:
    return PlaquetteLayer(
        QubitTemplate(),
        Plaquettes(FrozenDefaultDict({}, default_factory=empty_square_plaquette)),
    )


@pytest.fixture(name="raw_circuit_layer")
def raw_circuit_layer_fixture() -> RawCircuitLayer:
    return RawCircuitLayer(
        lambda k: ScheduledCircuit.from_circuit(stim.Circuit()),
        PhysicalQubitScalable2D(LinearFunction(4, 5), LinearFunction(4, 5)),
    )


def test_creation(
    plaquette_layer: PlaquetteLayer, raw_circuit_layer: RawCircuitLayer
) -> None:
    RepeatedLayer(plaquette_layer, LinearFunction(0, 1))
    RepeatedLayer(raw_circuit_layer, LinearFunction(1, 90))
    RepeatedLayer(
        SequencedLayers([plaquette_layer, plaquette_layer]), LinearFunction(1, 0)
    )
    with pytest.raises(TQECException, match=".*non-linear number of timesteps.*"):
        RepeatedLayer(
            RepeatedLayer(plaquette_layer, LinearFunction(1, 0)), LinearFunction(1, 0)
        )


def test_scalable_timesteps(plaquette_layer: PlaquetteLayer) -> None:
    assert RepeatedLayer(
        plaquette_layer, LinearFunction(0, 1)
    ).scalable_timesteps == LinearFunction(0, 1)
    assert RepeatedLayer(
        plaquette_layer, LinearFunction(1, 90)
    ).scalable_timesteps == LinearFunction(1, 90)
    assert RepeatedLayer(
        SequencedLayers([plaquette_layer, plaquette_layer]), LinearFunction(3, 5)
    ).scalable_timesteps == LinearFunction(6, 10)


@pytest.mark.parametrize("borders", [(border,) for border in SpatialBlockBorder])
def test_with_spatial_borders_trimmed(
    borders: tuple[SpatialBlockBorder, ...], plaquette_layer: PlaquetteLayer
) -> None:
    all_indices = frozenset(plaquette_layer.plaquettes.collection.keys())
    expected_plaquette_indices = all_indices - frozenset(
        itertools.chain.from_iterable(
            frozenset(
                plaquette_layer.template.get_border_indices(border.to_template_border())
            )
            for border in borders
        )
    )
    assert (
        frozenset(
            plaquette_layer.with_spatial_borders_trimmed(
                borders
            ).plaquettes.collection.keys()
        )
        == expected_plaquette_indices
    )


def test_to_sequenced_layer_with_schedule_simple(
    plaquette_layer: PlaquetteLayer,
) -> None:
    repeated_layer = RepeatedLayer(plaquette_layer, LinearFunction(2, 2))
    assert repeated_layer.to_sequenced_layer_with_schedule(
        (LinearFunction(0, 2), LinearFunction(2, 0))
    ) == SequencedLayers(
        [
            RepeatedLayer(plaquette_layer, LinearFunction(0, 2)),
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
        ]
    )
    assert repeated_layer.to_sequenced_layer_with_schedule(
        (LinearFunction(0, 1), LinearFunction(2, 0), LinearFunction(0, 1))
    ) == SequencedLayers(
        [
            plaquette_layer,
            RepeatedLayer(plaquette_layer, LinearFunction(2, 0)),
            plaquette_layer,
        ]
    )


def test_to_sequenced_layer_with_schedule(
    plaquette_layer: PlaquetteLayer,
) -> None:
    base = SequencedLayers([plaquette_layer, plaquette_layer, plaquette_layer])
    repeated_layer = RepeatedLayer(base, LinearFunction(2, 2))
    assert repeated_layer.to_sequenced_layer_with_schedule(
        (LinearFunction(0, 3), LinearFunction(6, 3))
    ) == SequencedLayers([base, RepeatedLayer(base, LinearFunction(2, 1))])
    assert repeated_layer.to_sequenced_layer_with_schedule(
        (LinearFunction(0, 3), LinearFunction(6, 0), LinearFunction(0, 3))
    ) == SequencedLayers([base, RepeatedLayer(base, LinearFunction(2, 0)), base])

    with pytest.raises(
        NotImplementedError,
        match="^The ability to split the body of a RepeatedLayer instance has not been implemented yet..*$",
    ):
        repeated_layer.to_sequenced_layer_with_schedule(
            (LinearFunction(0, 2), LinearFunction(6, 4))
        )


def test_to_sequenced_layer_with_schedule_raising(
    plaquette_layer: PlaquetteLayer,
) -> None:
    repeated_layer = RepeatedLayer(plaquette_layer, LinearFunction(2, 2))
    with pytest.raises(
        TQECException,
        match="Cannot transform the RepeatedLayer instance to a SequencedLayers instance with the provided schedule.*",
    ):
        repeated_layer.to_sequenced_layer_with_schedule(
            (LinearFunction(0, 2), LinearFunction(2, 0), LinearFunction(0, 2))
        )

    with pytest.raises(
        NotImplementedError,
        match="^Splitting a RepeatedLayer instance with a non-constant duration body is not implemented yet.$",
    ):
        RepeatedLayer(
            repeated_layer, LinearFunction(0, 2)
        ).to_sequenced_layer_with_schedule((LinearFunction(2, 2), LinearFunction(2, 2)))
