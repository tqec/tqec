from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

import stim

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.tree.annotations import LayerNodeAnnotations, Polygon
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction


def contains_only_layout_or_composed_layers(
    layers: Sequence[BaseLayer | BaseComposedLayer],
) -> TypeGuard[Sequence[LayoutLayer | BaseComposedLayer]]:
    """Ensure correct typing after using that function in a condition."""
    return all(isinstance(layer, (LayoutLayer, BaseComposedLayer)) for layer in layers)


class NodeWalker:
    def visit_node(self, node: LayerNode) -> None:
        """Interface called when ``node`` is visited, before recursing in children."""
        pass  # pragma: no cover

    def enter_node(self, node: LayerNode) -> None:
        """Interface called when entering ``node``."""
        pass

    def exit_node(self, node: LayerNode) -> None:
        """Interface called when exiting ``node``."""
        pass


class LayerNode:
    def __init__(
        self,
        layer: LayoutLayer | BaseComposedLayer,
        annotations: Mapping[int, LayerNodeAnnotations] | None = None,
    ) -> None:
        """Represent a node in a :class:`~tqec.compile.tree.tree.LayerTree`.

        Args:
            layer: layer being represented by the node.
            annotations: already computed annotations. Default to ``None`` meaning
                no annotations are provided. Should be a mapping from values of
                ``k`` to the annotations already computed for that value of ``k``.

        """
        self._layer = layer
        self._children = LayerNode._get_children(layer)
        self._annotations = dict(annotations) if annotations is not None else {}

    @staticmethod
    def _get_children(layer: LayoutLayer | BaseComposedLayer) -> list[LayerNode]:
        if isinstance(layer, LayoutLayer):
            return []
        if isinstance(layer, SequencedLayers):
            if not contains_only_layout_or_composed_layers(layer.layer_sequence):
                raise TQECError(
                    "Found a leaf node that is not an instance of "
                    f"{LayoutLayer.__name__}. This should not happen and is a "
                    "logical error."
                )
            return [LayerNode(lay) for lay in layer.layer_sequence]  # type: ignore
        if isinstance(layer, RepeatedLayer):
            if not isinstance(layer.internal_layer, LayoutLayer | BaseComposedLayer):
                raise TQECError(
                    "The layer that is being repeated is not an instance of "
                    f"{LayoutLayer.__name__} or {BaseComposedLayer.__name__}."
                )
            return [LayerNode(layer.internal_layer)]  # type: ignore
        if isinstance(layer, (PlaquetteLayer, RawCircuitLayer)):
            raise TQECError(
                f"Unsupported layer type found: {type(layer).__name__}. Expected "
                f"ALL leaf nodes to be of type {LayoutLayer.__name__}."
            )
        raise NotImplementedError(f"Unknown layer type found: {type(layer).__name__}.")

    @property
    def is_leaf(self) -> bool:
        """Return ``True`` if ``self`` does not have any children and so is a leaf node."""
        return isinstance(self._layer, LayoutLayer)

    @property
    def is_repeated(self) -> bool:
        """Return ``True`` if ``self`` stores a RepeatedLayer."""
        return isinstance(self._layer, RepeatedLayer)

    @property
    def repetitions(self) -> LinearFunction | None:
        """Return the number of repetitions of the node if ``self.is_repeated`` else ``None``."""
        return self._layer.repetitions if isinstance(self._layer, RepeatedLayer) else None

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of ``self``."""
        return {  # pragma: no cover
            "layer": type(self._layer).__name__,
            "children": [child.to_dict() for child in self._children],
            "annotations": {k: annotation.to_dict() for k, annotation in self._annotations.items()},
        }

    def walk(self, walker: NodeWalker) -> None:
        """Walk the tree using Depth-First Search (DFS), calling walker methods on each node.

        Args:
            walker: structure that will be called on each explored node.

        """
        walker.enter_node(self)
        walker.visit_node(self)
        for child in self._children:
            child.walk(walker)
        walker.exit_node(self)

    @property
    def children(self) -> list[LayerNode]:
        """Return the children nodes of ``self``."""
        return self._children

    def get_annotations(self, k: int) -> LayerNodeAnnotations:
        """Return the annotations associated with the provided scaling parameter ``k``."""
        return self._annotations.setdefault(k, LayerNodeAnnotations())

    def set_circuit_annotation(self, k: int, circuit: ScheduledCircuit) -> None:
        """Set the circuit annotation associated with the scaling parameter ``k`` to ``circuit``."""
        self.get_annotations(k).circuit = circuit

    def generate_circuits_with_potential_polygons(
        self,
        k: int,
        global_qubit_map: QubitMap,
        add_polygons: bool = False,
    ) -> list[stim.Circuit | list[Polygon]]:
        """Generate the circuits and polygons for each nodes in the subtree rooted at ``self``.

        Args:
            k: scaling parameter.
            global_qubit_map: qubit map that should be used to generate the
                quantum circuit. Qubits from the returned quantum circuit will
                adhere to the provided qubit map.
            add_polygons: if ``True``, polygon objects for visualization in Crumble
                will be added to the returned list.

        Returns:
            a list of ``stim.Circuit`` and/or ``list[Polygon]`` objects.
            Each ``stim.Circuit`` represents a quantum circuit of a leaf node in
            the tree. Each polygon list represents the stabilizer configuration
            for the corresponding leaf node and will be placed right before the
            corresponding circuit in the returned list. If two consecutive leaf
            nodes have the same stabilizer configuration, only the first polygons
            will be kept.

        """
        if isinstance(self._layer, LayoutLayer):
            annotations = self.get_annotations(k)
            base_circuit = annotations.circuit
            if base_circuit is None:
                raise TQECError(
                    "Cannot generate the final quantum circuit before annotating "
                    "nodes with their individual circuits. Did you call "
                    "LayerTree.annotate_circuits before?"
                )
            local_qubit_map = base_circuit.qubit_map
            qubit_indices_mapping = {
                local_qubit_map[q]: global_qubit_map[q] for q in local_qubit_map.qubits
            }
            mapped_circuit = base_circuit.map_qubit_indices(qubit_indices_mapping)
            for annotation in annotations.detectors + annotations.observables:
                mapped_circuit.append_annotation(annotation.to_instruction())
            mapped_circuit.append_annotation(
                stim.CircuitInstruction(
                    "SHIFT_COORDS", [], StimCoordinates(0, 0, 1).to_stim_coordinates()
                )
            )
            ret: list[stim.Circuit | list[Polygon]] = [
                mapped_circuit.get_circuit(include_qubit_coords=False)
            ]
            if add_polygons:
                ret.insert(0, annotations.polygons)

            return ret

        if isinstance(self._layer, SequencedLayers):
            ret = []
            for child, next_child in itertools.pairwise(self._children):
                ret += child.generate_circuits_with_potential_polygons(
                    k, global_qubit_map, add_polygons
                )
                if not next_child.is_repeated:
                    assert isinstance(ret[-1], stim.Circuit)
                    ret[-1].append("TICK", [], [])
            ret += self._children[-1].generate_circuits_with_potential_polygons(
                k, global_qubit_map, add_polygons
            )
            return ret

        if isinstance(self._layer, RepeatedLayer):
            body = self._children[0].generate_circuits_with_potential_polygons(
                k, global_qubit_map, add_polygons=add_polygons
            )
            body_circuit = sum(
                (i for i in body if isinstance(i, stim.Circuit)),
                start=stim.Circuit(),
            )
            body_circuit.insert(0, stim.CircuitInstruction("TICK"))
            ret = []
            if add_polygons:
                # only keep the first set of polygons
                ret.append(body[0])
            ret.append(body_circuit * self._layer.repetitions.integer_eval(k))
            return ret
        raise TQECError(f"Unknown layer type found: {type(self._layer).__name__}.")

    def generate_circuit(self, k: int, global_qubit_map: QubitMap) -> stim.Circuit:
        """Generate the quantum circuit representing the node.

        Args:
            k: scaling parameter.
            global_qubit_map: qubit map that should be used to generate the
                quantum circuit. Qubits from the returned quantum circuit will
                adhere to the provided qubit map.

        Returns:
            a ``stim.Circuit`` instance representing ``self`` with the provided
            ``global_qubit_map``.

        """
        circuits = self.generate_circuits_with_potential_polygons(
            k, global_qubit_map, add_polygons=False
        )
        ret = stim.Circuit()
        for circuit in circuits:
            assert isinstance(circuit, stim.Circuit)
            ret += circuit
        return ret
