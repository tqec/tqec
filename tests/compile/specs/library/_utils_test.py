import pytest

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.library._utils import _get_block
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.qubit import QubitTemplate
from tqec.utils.enums import Basis
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction


def _recording_plaquettes_generator():
    calls: list[tuple[bool, Basis | None, Basis | None]] = []
    generated_plaquettes: list[Plaquettes] = []

    def generate(is_reversed: bool, reset: Basis | None, measurement: Basis | None) -> Plaquettes:
        calls.append((is_reversed, reset, measurement))
        plaquettes = Plaquettes(FrozenDefaultDict({}))
        generated_plaquettes.append(plaquettes)
        return plaquettes

    return generate, calls, generated_plaquettes


def test_get_block_without_spatial_junction_uses_forward_schedule() -> None:
    generate, calls, generated = _recording_plaquettes_generator()
    repetitions = LinearFunction(4, 2)

    block = _get_block(Basis.Z, False, QubitTemplate(), generate, repetitions)

    assert isinstance(block, Block)
    assert len(block.layer_sequence) == 3
    assert isinstance(block.layer_sequence[1], RepeatedLayer)
    assert block.layer_sequence[1].repetitions == repetitions
    assert isinstance(block.layer_sequence[0], PlaquetteLayer)
    assert block.layer_sequence[0].plaquettes is generated[0]
    assert isinstance(block.layer_sequence[1].internal_layer, PlaquetteLayer)
    assert block.layer_sequence[1].internal_layer.plaquettes is generated[1]
    assert isinstance(block.layer_sequence[2], PlaquetteLayer)
    assert block.layer_sequence[2].plaquettes is generated[2]
    assert calls == [
        (False, Basis.Z, None),
        (False, None, None),
        (False, None, Basis.Z),
        (True, None, None),
        (True, None, Basis.Z),
    ]


def test_get_block_junction_even_slope_even_offset_alternates_and_measures_reversed() -> None:
    generate, _, generated = _recording_plaquettes_generator()

    block = _get_block(Basis.Z, True, QubitTemplate(), generate, LinearFunction(4, 2))

    assert len(block.layer_sequence) == 3
    assert isinstance(block.layer_sequence[1], SequencedLayers)
    repeated_alternation = block.layer_sequence[1].layer_sequence[0]
    assert isinstance(repeated_alternation, RepeatedLayer)
    assert repeated_alternation.repetitions == LinearFunction(2, 1)
    assert isinstance(repeated_alternation.internal_layer, SequencedLayers)
    alternating_layers = repeated_alternation.internal_layer.layer_sequence
    assert isinstance(alternating_layers[0], PlaquetteLayer)
    assert alternating_layers[0].plaquettes is generated[3]
    assert isinstance(alternating_layers[1], PlaquetteLayer)
    assert alternating_layers[1].plaquettes is generated[1]
    assert isinstance(block.layer_sequence[-1], PlaquetteLayer)
    assert block.layer_sequence[-1].plaquettes is generated[4]


def test_get_block_junction_even_slope_odd_offset_appends_reversed_and_measures_forward() -> None:
    generate, _, generated = _recording_plaquettes_generator()

    block = _get_block(Basis.Z, True, QubitTemplate(), generate, LinearFunction(4, 3))

    assert len(block.layer_sequence) == 3
    assert isinstance(block.layer_sequence[1], SequencedLayers)
    loop_layers = block.layer_sequence[1].layer_sequence
    assert len(loop_layers) == 2
    repeated_alternation = loop_layers[0]
    assert isinstance(repeated_alternation, RepeatedLayer)
    assert repeated_alternation.repetitions == LinearFunction(2, 1)
    assert isinstance(repeated_alternation.internal_layer, SequencedLayers)
    alternating_layers = repeated_alternation.internal_layer.layer_sequence
    assert isinstance(alternating_layers[0], PlaquetteLayer)
    assert alternating_layers[0].plaquettes is generated[3]
    assert isinstance(alternating_layers[1], PlaquetteLayer)
    assert alternating_layers[1].plaquettes is generated[1]
    assert isinstance(loop_layers[1], PlaquetteLayer)
    assert loop_layers[1].plaquettes is generated[3]
    assert isinstance(block.layer_sequence[-1], PlaquetteLayer)
    assert block.layer_sequence[-1].plaquettes is generated[2]


def test_get_block_junction_odd_slope_raises_not_implemented() -> None:
    generate, _, _ = _recording_plaquettes_generator()

    with pytest.raises(NotImplementedError, match="odd slope"):
        _get_block(Basis.Z, True, QubitTemplate(), generate, LinearFunction(3, 2))
