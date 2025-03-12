from typing import Any, Mapping

from typing import Any

from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.tree.annotations import LayerTreeAnnotations
from tqec.compile.tree.node import LayerNode


class LayerTree:
    def __init__(
        self,
        root: SequencedLayers,
        annotations: Mapping[int, LayerTreeAnnotations] | None = None,
    ):
        self._root = LayerNode(root)
        self._annotations = dict(annotations) if annotations is not None else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self._root.to_dict(),
            "annotations": {
                k: annotation.to_dict() for k, annotation in self._annotations.items()
            },
        }
        return {"root": self._root.to_dict()}

    def annotate_observable(self, observable: AbstractObservable) -> None:
        pass

    def annotate_detectors(
        self,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
    ) -> None:
        pass

    def get_annotation(self, k: int) -> LayerTreeAnnotations:
        return self._annotations.setdefault(k, LayerTreeAnnotations())

    def set_qubit_map_annotation(self, k: int, qubit_map: QubitMap) -> None:
        self.get_annotation(k).qubit_map = qubit_map
