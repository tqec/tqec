from __future__ import annotations

from typing import Any, Mapping, Sequence, TypeGuard

import stim

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.tree.annotations import LayerNodeAnnotations
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECException


def contains_only_layout_or_composed_layers(
    layers: Sequence[BaseLayer | BaseComposedLayer],
) -> TypeGuard[Sequence[LayoutLayer | BaseComposedLayer]]:
    return all(isinstance(layer, (LayoutLayer, BaseComposedLayer)) for layer in layers)


class NodeWalkerInterface:
    def visit_node(self, node: LayerNode) -> None:
        pass


class LayerNode:
    def __init__(
        self,
        layer: LayoutLayer | BaseComposedLayer,
        annotations: Mapping[int, LayerNodeAnnotations] | None = None,
    ) -> None:
        """Represents a node in a :class:`LayerTree`.

        Args:
            layer: layer being represented by the node.
            annotations: already computed annotations. Default to ``None`` meaning
                no annotations are provided.
        """
        self._layer = layer
        # If the node is a leaf node, a time order can be assigned to it.
        # The order is used to determine the order in which the layer happens
        # in the final circuit.
        self._time_order: int | None = None
        self._children: list[LayerNode] = self._create_children(layer)
        self._annotations = dict(annotations) if annotations is not None else {}

    @property
    def order(self) -> int | None:
        return self._time_order

    @order.setter
    def order(self, value: int | None) -> None:
        self._time_order = value

    @staticmethod
    def _create_children(layer: BaseLayer | BaseComposedLayer) -> list[LayerNode]:
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
                    f"Repeated layer is not an instance of {LayoutLayer.__name__} "
                    f"or {BaseComposedLayer.__name__}."
                )
            return [LayerNode(layer.internal_layer)]
        raise TQECException(f"Unknown layer type found: {type(layer).__name__}.")

    def get_children(self, recursive: bool = False) -> list[LayerNode]:
        """Get the children of the node. If ``recursive`` is set to ``True``, then
        a depth-first search is performed to get all the children of the node.

        DFS traversal guarantees that the leaf nodes are returned in the correct
        time order.
        """
        if not recursive:
            return [child for child in self._children]
        ret: list[LayerNode] = []
        for child in self._children:
            ret.append(child)
            ret.extend(child.get_children(recursive=True))
        return ret

    @property
    def is_leaf(self) -> bool:
        """Returns ``True`` if ``self`` does not have any children and so is a
        leaf node."""
        return isinstance(self._layer, LayoutLayer)

    @property
    def is_repeated(self) -> bool:
        """Returns ``True`` if ``self`` stores a RepeatedLayer."""
        return isinstance(self._layer, RepeatedLayer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": type(self._layer).__name__,
            "children": [child.to_dict() for child in self._children],
            "annotations": {
                k: annotation.to_dict() for k, annotation in self._annotations.items()
            },
        }

    def walk(self, walker: NodeWalkerInterface) -> None:
        walker.visit_node(self)
        for child in self._children:
            child.walk(walker)

    def get_annotations(self, k: int) -> LayerNodeAnnotations:
        return self._annotations.setdefault(k, LayerNodeAnnotations())

    def set_circuit_annotation(self, k: int, circuit: ScheduledCircuit) -> None:
        self.get_annotations(k).circuit = circuit

    def generate_circuit(
        self,
        k: int,
        global_qubit_map: QubitMap,
        shift_coords: StimCoordinates | None = None,
    ) -> stim.Circuit:
        if isinstance(self._layer, LayoutLayer):
            annotations = self.get_annotations(k)
            base_circuit = annotations.circuit
            if base_circuit is None:
                raise TQECException(
                    "Cannot generate the final quantum circuit before annotating "
                    "nodes with their individual circuits. Did you call "
                    "LayerTree.annotate_circuits before?"
                )
            local_qubit_map = base_circuit.qubit_map
            qubit_indices_mapping = {
                local_qubit_map[q]: global_qubit_map[q] for q in local_qubit_map.qubits
            }
            mapped_circuit = base_circuit.map_qubit_indices(qubit_indices_mapping)
            if shift_coords is not None:
                mapped_circuit.append_annotation(
                    stim.CircuitInstruction(
                        "SHIFT_COORDS", [], shift_coords.to_stim_coordinates()
                    )
                )
            for annotation in annotations.detectors + annotations.observables:
                mapped_circuit.append_annotation(annotation.to_instruction())
            return mapped_circuit.get_circuit(include_qubit_coords=False)
        if isinstance(self._layer, SequencedLayers):
            ret = stim.Circuit()
            for child, next in zip(self._children[:-1], self._children[1:]):
                ret += child.generate_circuit(k, global_qubit_map)
                if not next.is_repeated:
                    ret.append("TICK")
            ret += self._children[-1].generate_circuit(k, global_qubit_map)
            return ret
        if isinstance(self._layer, RepeatedLayer):
            body = self._children[0].generate_circuit(
                k,
                global_qubit_map,
                shift_coords=StimCoordinates(
                    0, 0, self._layer.internal_layer.timesteps(k)
                ),
            )
            body.insert(0, stim.CircuitInstruction("TICK"))
            ret = stim.Circuit()
            ret.append(
                stim.CircuitRepeatBlock(self._layer.repetitions.integer_eval(k), body)
            )
            return ret
        raise TQECException(f"Unknown layer type found: {type(self._layer).__name__}.")
