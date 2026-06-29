from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator, Mapping, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any, TypeGuard

import stim

if TYPE_CHECKING:
    from tqec.compile.tree.annotators.detectors import AnnotateDetectorsOnLayerNode

from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    ObservableBuilder,
    ObservableComponent,
)
from tqec.compile.tree.annotations import LayerNodeAnnotations, Polygon
from tqec.compile.tree.annotators.observables import (
    _annotate_observable_at_node,
    get_ordered_leaves,
)
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
            return [LayerNode(lay) for lay in layer.layer_sequence]
        if isinstance(layer, RepeatedLayer):
            if not isinstance(layer.internal_layer, LayoutLayer | BaseComposedLayer):
                raise TQECError(
                    "The layer that is being repeated is not an instance of "
                    f"{LayoutLayer.__name__} or {BaseComposedLayer.__name__}."
                )
            return [LayerNode(layer.internal_layer)]
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
        return list(
            self._generate_circuits_with_potential_polygons_stream(
                k, global_qubit_map, add_polygons=add_polygons
            )
        )

    def _generate_circuits_with_potential_polygons_stream(
        self,
        k: int,
        global_qubit_map: QubitMap,
        add_polygons: bool = False,
        reschedule_measurements: bool = False,
        detectors_walker: AnnotateDetectorsOnLayerNode | None = None,
        subtree_to_z: dict[LayerNode, int] | None = None,
        abstract_observables: list[AbstractObservable] | None = None,
        observable_builder: ObservableBuilder | None = None,
        leaf_dict: dict[LayerNode, list[tuple[Callable, ObservableComponent]]] | None = None,
    ) -> Iterator[stim.Circuit | list[Polygon]]:
        """Generate the circuits and polygons for each nodes in the subtree rooted at ``self``.

        Args:
            k: scaling parameter.
            global_qubit_map: qubit map that should be used to generate the
                quantum circuit. Qubits from the returned quantum circuit will
                adhere to the provided qubit map.
            reschedule_measurements: if ``True``, measurements will be rescheduled
                to optimize circuit execution.
            detectors_walker: walker instance used to compute and annotate detectors
                on leaf nodes during circuit generation.
            subtree_to_z: mapping from direct children of root to their z-coordinate values,
                used for determining which abstract observables to apply at each node.
            abstract_observables: collection of abstract observable definitions to be
                annotated in the circuit.
            observable_builder: builder instance used to construct observable annotations
                from abstract observable definitions.
            add_polygons: if ``True``, polygon objects for visualization in Crumble
                will be added to the returned list.
            leaf_dict: optional dictionary mapping leaf nodes to lists of observable functions
                that should be applied during node processing. Default to ``None``.

        Returns:
            an iterator to ``stim.Circuit`` and/or ``list[Polygon]`` objects.
            Each ``stim.Circuit`` represents a quantum circuit of a leaf node in
            the tree. Each polygon list represents the stabilizer configuration
            for the corresponding leaf node and will be placed right before the
            corresponding circuit in the returned list. If two consecutive leaf
            nodes have the same stabilizer configuration, only the first polygons
            will be kept.

        """
        pre_annotated = (
            subtree_to_z is None or abstract_observables is None or observable_builder is None
        )

        if not pre_annotated and detectors_walker is not None:
            detectors_walker.enter_node(self)

        try:
            if isinstance(self._layer, LayoutLayer):
                annotations = self.get_annotations(k)

                if not pre_annotated:
                    # circuit
                    annotations.circuit = self._layer.to_circuit(
                        k, reschedule_measurements=reschedule_measurements
                    )

                    # detectors
                    if detectors_walker is not None:
                        detectors_walker.visit_node(self)

                    # observables
                    if leaf_dict is not None:
                        fns = leaf_dict.get(self)
                        if fns is not None:
                            for fn, component in fns:
                                fn(self, component=component)

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

                if add_polygons:
                    yield annotations.polygons

                yield mapped_circuit.get_circuit(include_qubit_coords=False)

            elif isinstance(self._layer, SequencedLayers):
                leaf_dict: dict[LayerNode, list[tuple[Callable, ObservableComponent]]] = {}

                if not pre_annotated:
                    if self in subtree_to_z:
                        z = subtree_to_z[self]
                        leaves = get_ordered_leaves(self)

                        for obs_idx, observable in enumerate(abstract_observables):
                            obs_slice = observable.slice_at_z(z)

                            ao_partial = partial(
                                _annotate_observable_at_node,
                                obs_slice=obs_slice,
                                k=k,
                                observable_index=obs_idx,
                                observable_builder=observable_builder,
                            )

                            if leaves[0] not in leaf_dict:
                                leaf_dict[leaves[0]] = []
                            leaf_dict[leaves[0]].append(
                                (ao_partial, ObservableComponent.BOTTOM_STABILIZERS)
                            )

                            readout_layer = leaves[-1]
                            if obs_slice.temporal_hadamard_pipes:
                                readout_layer = leaves[-2]

                                if leaves[-1] not in leaf_dict:
                                    leaf_dict[leaves[-1]] = []
                                leaf_dict[leaves[-1]].append(
                                    (ao_partial, ObservableComponent.REALIGNMENT)
                                )

                            if readout_layer not in leaf_dict:
                                leaf_dict[readout_layer] = []
                            leaf_dict[readout_layer].append(
                                (ao_partial, ObservableComponent.TOP_READOUTS)
                            )

                for child, next_child in itertools.pairwise(self._children):
                    circ = child._generate_circuits_with_potential_polygons_stream(
                        k,
                        global_qubit_map,
                        add_polygons,
                        reschedule_measurements,
                        detectors_walker,
                        subtree_to_z,
                        abstract_observables,
                        observable_builder,
                        leaf_dict=leaf_dict,
                    )

                    if not next_child.is_repeated:
                        tick = stim.Circuit()
                        tick.append("TICK", [], [])
                        circ = itertools.chain(
                            circ, [tick]
                        )  # add TICK at the end if next child is not repeated

                    yield from circ

                yield from self._children[-1]._generate_circuits_with_potential_polygons_stream(
                    k,
                    global_qubit_map,
                    add_polygons,
                    reschedule_measurements,
                    detectors_walker,
                    subtree_to_z,
                    abstract_observables,
                    observable_builder,
                    leaf_dict=leaf_dict,
                )

            elif isinstance(self._layer, RepeatedLayer):
                body = list(
                    self._children[0]._generate_circuits_with_potential_polygons_stream(
                        k,
                        global_qubit_map,
                        add_polygons=add_polygons,
                        reschedule_measurements=reschedule_measurements,
                        detectors_walker=detectors_walker,
                        subtree_to_z=subtree_to_z,
                        abstract_observables=abstract_observables,
                        observable_builder=observable_builder,
                    )
                )
                body_circuit = sum(
                    (i for i in body if isinstance(i, stim.Circuit)),
                    start=stim.Circuit(),
                )
                body_circuit.insert(0, stim.CircuitInstruction("TICK"))

                if add_polygons:
                    yield body[0]  # only keep the first set of polygons

                yield body_circuit * self._layer.repetitions.integer_eval(k)

            else:
                raise TQECError(f"Unknown layer type found: {type(self._layer).__name__}.")
        finally:
            if not pre_annotated and detectors_walker is not None:
                detectors_walker.exit_node(self)

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
        circuit = stim.Circuit()
        stream = self._generate_circuit_stream(k, global_qubit_map)
        for circ in stream:
            circuit.append(circ)
        return circuit

    def _generate_circuit_stream(
        self,
        k: int,
        global_qubit_map: QubitMap,
        reschedule_measurements: bool = False,
        detectors_walker: AnnotateDetectorsOnLayerNode | None = None,
        subtree_to_z: dict[LayerNode, int] | None = None,
        abstract_observables: list[AbstractObservable] | None = None,
        observable_builder: ObservableBuilder | None = None,
    ) -> Iterator[stim.Circuit]:
        """Generate the quantum circuit representing the node.

        Args:
            k: scaling parameter.
            global_qubit_map: qubit map that should be used to generate the
                quantum circuit. Qubits from the returned quantum circuit will
                adhere to the provided qubit map.
            reschedule_measurements: if ``True``, measurements will be rescheduled
                to optimize circuit execution.
            detectors_walker: walker instance used to compute and annotate detectors
                on leaf nodes during circuit generation.
            subtree_to_z: mapping from direct children of root to their z-coordinate values,
                used for determining which abstract observables to apply at each node.
            abstract_observables: collection of abstract observable definitions to be
                annotated in the circuit.
            observable_builder: builder instance used to construct observable annotations
                from abstract observable definitions.

        Returns:
            a ``stim.Circuit`` instance representing ``self`` with the provided
            ``global_qubit_map``.

        """
        circuits = self._generate_circuits_with_potential_polygons_stream(
            k,
            global_qubit_map,
            add_polygons=False,
            reschedule_measurements=reschedule_measurements,
            detectors_walker=detectors_walker,
            subtree_to_z=subtree_to_z,
            abstract_observables=abstract_observables,
            observable_builder=observable_builder,
        )

        # remove polygons from the stream and yield only circuits
        for item in circuits:
            if isinstance(item, stim.Circuit):
                yield item
