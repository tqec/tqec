from __future__ import annotations

from typing import Any

from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.tree.annotations import LayerTreeAnnotations
from tqec.compile.tree.node import LayerNode


class LayerTree:
    def __init__(
        self, root: SequencedLayers, annotations: LayerTreeAnnotations | None = None
    ):
        self._root = LayerNode(root)
        self._annotations = annotations or LayerTreeAnnotations()

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
