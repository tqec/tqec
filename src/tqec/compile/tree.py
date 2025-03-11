from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, TypeGuard

import stim

from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECException


def contains_only_layout_or_composed_layers(
    layers: Sequence[BaseLayer | BaseComposedLayer],
) -> TypeGuard[Sequence[LayoutLayer | BaseComposedLayer]]:
    return all(isinstance(layer, (LayoutLayer, BaseComposedLayer)) for layer in layers)


@dataclass(frozen=True)
class DetectorAnnotation:
    """An annotation that should include all the necessary information to build a
    DETECTOR instruction.

    Todo:
        Will change according to the needs.
    """

    coordinates: StimCoordinates
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "DETECTOR",
            [stim.target_rec(offset) for offset in self.measurement_offsets],
            self.coordinates.to_stim_coordinates(),
        )


@dataclass(frozen=True)
class ObservableAnnotation:
    """An annotation that should include all the necessary information to build a
    OBSERVABLE_INCLUDE instruction.

    Todo:
        Will change according to the needs.
    """

    observable_index: int
    measurement_offsets: list[int]

    def __post_init__(self) -> None:
        if any(m >= 0 for m in self.measurement_offsets):
            raise TQECException("Expected strictly negative measurement offsets.")

    def to_instruction(self) -> stim.CircuitInstruction:
        return stim.CircuitInstruction(
            "OBSERVABLE_INCLUDE",
            [stim.target_rec(offset) for offset in self.measurement_offsets],
            [self.observable_index],
        )


class LayerNode:
    def __init__(
        self,
        layer: LayoutLayer | BaseComposedLayer,
        annotations: list[DetectorAnnotation | ObservableAnnotation] | None = None,
    ):
        """Represents a node in a :class:`LayerTree`.

        Args:
            layer: layer being represented by the node.
            annotations: already computed annotations if available. Annotations
                can be added a posteriori with :meth:`LayerNode.append_annotation`.
        """
        self._layer = layer
        self._children = LayerNode._get_children(layer)
        self._annotations = annotations or []

    @property
    def is_leaf(self) -> bool:
        """Returns ``True`` if ``self`` does not have any children and so is a
        leaf node."""
        return isinstance(self._layer, LayoutLayer)

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": type(self._layer).__name__,
            "children": [child.to_dict() for child in self._children],
            "annotations": self._annotations,
        }

    def append_annotation(
        self, annotation: DetectorAnnotation | ObservableAnnotation
    ) -> None:
        """Append the provided annotation to the list of annotations."""
        self._annotations.append(annotation)

    def to_circuit(self) -> stim.Circuit:
        circuit = stim.Circuit()
        # Get the raw circuit
        if isinstance(self._layer, LayoutLayer):
            circuit = self._layer.to_circuit()
        else:
            assert not self.is_leaf
            for child in self._children:
                circuit += child.to_circuit()
        # Append the annotations
        for annotation in self._annotations:
            circuit.append(annotation.to_instruction())
        return circuit


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
