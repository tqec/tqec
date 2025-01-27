from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.sequenced import SequencedLayers


class ReversedLayers(SequencedLayers):
    def __init__(self, forward_layer: BaseLayer, backward_layer: BaseLayer) -> None:
        super().__init__([forward_layer, backward_layer])
