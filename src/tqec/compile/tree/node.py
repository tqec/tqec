from __future__ import annotations

from typing import Any, Sequence, TypeGuard

from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.tree.annotations import LayerNodeAnnotations
from tqec.utils.exceptions import TQECException


def contains_only_layout_or_composed_layers(
    layers: Sequence[BaseLayer | BaseComposedLayer],
) -> TypeGuard[Sequence[LayoutLayer | BaseComposedLayer]]:
    return all(isinstance(layer, (LayoutLayer, BaseComposedLayer)) for layer in layers)


class LayerNode:
    def __init__(
        self,
        layer: LayoutLayer | BaseComposedLayer,
        annotations: LayerNodeAnnotations | None = None,
    ):
        """Represents a node in a :class:`LayerTree`.

        Args:
            layer: layer being represented by the node.
            annotations: already computed annotations. Default to ``None`` meaning
                no annotations are provided.
        """
        self._layer = layer
        self._children = LayerNode._get_children(layer)
        self._annotations = annotations or LayerNodeAnnotations()

    @staticmethod
    def _get_children(layer: LayoutLayer | BaseComposedLayer) -> list[LayerNode]:
        if isinstance(layer, LayoutLayer):
            return []
        if isinstance(layer, SequencedLayers):
            if not contains_only_layout_or_composed_layers(layer.layer_sequence):
                raise TQECException(
                    "Found a leaf node that is not an instance of "
                    f"{LayoutLayer.__name__}. This should not happen and is a "
                    "logical error."
                )
            return [LayerNode(lay) for lay in layer.layer_sequence]
        if isinstance(layer, RepeatedLayer):
            if not isinstance(layer.internal_layer, LayoutLayer | BaseComposedLayer):
                raise TQECException(
                    f"Repeated layer is not an instance of {LayoutLayer.__name__}."
                )
            return [LayerNode(layer.internal_layer)]
        raise TQECException(f"Unknown layer type found: {type(layer).__name__}.")

    @property
    def is_leaf(self) -> bool:
        """Returns ``True`` if ``self`` does not have any children and so is a
        leaf node."""
        return isinstance(self._layer, LayoutLayer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": type(self._layer).__name__,
            "children": [child.to_dict() for child in self._children],
            "annotations": self._annotations,
        }
