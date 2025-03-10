from __future__ import annotations

from abc import ABC
from typing import Any, Sequence, TypeGuard

import stim

from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.detector import Detector
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.utils.exceptions import TQECException


def contains_only_layout_or_composed_layers(
    layers: Sequence[BaseLayer | BaseComposedLayer],
) -> TypeGuard[Sequence[LayoutLayer | BaseComposedLayer]]:
    return all(isinstance(layer, (LayoutLayer, BaseComposedLayer)) for layer in layers)


class LayerNode(ABC):
    def __init__(
        self,
        layer: LayoutLayer | BaseComposedLayer,
        detector_annotations: list[Detector] | None = None,
        observable_include_annotation: list[stim.CircuitInstruction] | None = None,
    ):
        super().__init__()
        self._layer = layer
        self._children = LayerNode._get_children(layer)
        self._detector_annotations = detector_annotations or []
        self._observable_include_annotation = observable_include_annotation or []

    @property
    def is_leaf(self) -> bool:
        return isinstance(self._layer, LayoutLayer)

    @staticmethod
    def _get_children(layer: LayoutLayer | BaseComposedLayer) -> list[LayerNode]:
        if isinstance(layer, LayoutLayer):
            return []
        if isinstance(layer, SequencedLayers):
            if not contains_only_layout_or_composed_layers(layer.layer_sequence):
                raise TQECException()
            return [LayerNode(lay) for lay in layer.layer_sequence]
        if isinstance(layer, RepeatedLayer):
            if not isinstance(layer.internal_layer, LayoutLayer | BaseComposedLayer):
                raise TQECException()
            return [LayerNode(layer.internal_layer)]
        raise TQECException(f"Unknown layer type found: {type(layer).__name__}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": type(self._layer).__name__,
            "children": [child.to_dict() for child in self._children],
            "detectors": self._detector_annotations,
            "observables": self._observable_include_annotation,
        }


class LayerTree:
    def __init__(self, root: SequencedLayers):
        self._root = LayerNode(root)

    def to_dict(self) -> dict[str, Any]:
        return {"root": self._root.to_dict()}

    def annotate_observable(self, observable: AbstractObservable) -> None:
        pass

    def annotate_detectors(
        self,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
    ) -> None:
        pass
