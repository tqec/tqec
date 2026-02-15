from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator, Mapping, Sequence
from functools import partial
from typing import Any, TypeGuard

import stim
from typing_extensions import override

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors import DetectorDatabase, compute_detectors_for_fixed_radius
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    ObservableBuilder,
    ObservableComponent,
    get_observable_with_measurement_records,
)
from tqec.compile.tree.annotations import DetectorAnnotation, LayerNodeAnnotations, Polygon
from tqec.compile.tree.annotators.detectors import LookbackStack
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


class AnnotateDetectorsOnLayerNode(NodeWalker):
    def __init__(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        only_use_database: bool = False,
        lookback: int = 2,
        parallel_process_count: int = 1,
    ):
        """Walker computing and annotating detectors on leaf nodes.

        This class keeps track of the ``lookback`` previous leaf nodes seen and
        uses them to automatically compute the detectors at all the leaf nodes
        it encounters.

        Args:
            k: scaling factor.
            manhattan_radius: Parameter for the automatic computation of detectors.
                Should be large enough so that flows cancelling each other to
                form a detector are strictly contained in plaquettes that are at
                most at a distance of ``manhattan_radius`` from the central
                plaquette. Detector computation runtime grows with this parameter,
                so you should try to keep it to its minimum. A value too low might
                produce invalid detectors.
            detector_database: existing database of detectors that is used to
                avoid computing detectors if the database already contains them.
                Default to `None` which result in not using any kind of database
                and unconditionally performing the detector computation.
            only_use_database: if ``True``, only detectors from the database will be
                used. An error will be raised if a situation that is not registered
                in the database is encountered. Default to ``False``.
            lookback: number of QEC rounds to consider to try to find detectors. Including more
                rounds increases computation time.
            parallel_process_count: number of processes to use for parallel processing.
                1 for sequential processing, >1 for parallel processing using
                ``parallel_process_count`` processes, and -1 for using all available
                CPU cores. Default to 1.

        """
        if lookback < 1:
            raise TQECError(
                "Cannot compute detectors without any layer. The `lookback` "
                f"parameter should be >= 1 but got {lookback}."
            )
        self._k = k
        self._manhattan_radius = manhattan_radius
        self._database = detector_database if detector_database is not None else DetectorDatabase()
        self._only_use_database = only_use_database
        self._lookback_size = lookback
        self._lookback_stack = LookbackStack()
        self._parallel_process_count = parallel_process_count

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not isinstance(node._layer, LayoutLayer):
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECError("Cannot compute detectors without the circuit annotation.")
        self._lookback_stack.append(
            *node._layer.to_template_and_plaquettes(),
            MeasurementRecordsMap.from_scheduled_circuit(annotations.circuit),
        )
        templates, plaquettes, measurement_records = self._lookback_stack.lookback(
            self._lookback_size
        )

        detectors = compute_detectors_for_fixed_radius(
            templates,
            self._k,
            plaquettes,
            self._manhattan_radius,
            self._database,
            self._only_use_database,
            self._parallel_process_count,
        )

        for detector in detectors:
            annotations.detectors.append(
                DetectorAnnotation.from_detector(detector, measurement_records)
            )

    @override
    def enter_node(self, node: LayerNode) -> None:
        if node.is_repeated:
            self._lookback_stack.enter_repeat_block()

    @override
    def exit_node(self, node: LayerNode) -> None:
        if not node.is_repeated:
            return
        # Note: this is the place to perform checks. In particular, checking that
        # detectors computed at the first repetition of the REPEAT block are also
        # valid at any repetitions. This is a requirement for the REPEAT block to
        # make sense, but that would be nice to include a check to avoid
        # misleadingly include detectors that are incorrect sometimes.
        repetitions = node.repetitions
        assert repetitions is not None
        self._lookback_stack.close_repeat_block(repetitions.integer_eval(self._k))


def _get_ordered_leaves(root: LayerNode) -> list[LayerNode]:
    """Return the leaves of the tree in time order."""
    if root.is_leaf:
        return [root]
    return [n for child in root.children for n in _get_ordered_leaves(child)]


def _annotate_observable_at_node(
    node: LayerNode,
    obs_slice: AbstractObservable,
    k: int,
    observable_index: int,
    observable_builder: ObservableBuilder,
    component: ObservableComponent,
) -> None:
    circuit = node.get_annotations(k).circuit
    assert circuit is not None
    measurement_record = MeasurementRecordsMap.from_scheduled_circuit(circuit)
    assert isinstance(node._layer, LayoutLayer)
    template, _ = node._layer.to_template_and_plaquettes()
    obs_qubits = observable_builder.build(k, template, obs_slice, component)
    if obs_qubits:
        obs_annotation = get_observable_with_measurement_records(
            obs_qubits, measurement_record, observable_index
        )
        node.get_annotations(k).observables.append(obs_annotation)


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

    def generate_circuits_with_potential_polygons_stream(
        self,
        k: int,
        global_qubit_map: QubitMap,
        reschedule_measurements: bool,
        detectors_walker: AnnotateDetectorsOnLayerNode,
        subtree_to_z: dict[
            LayerNode, int
        ],  # Maybe this doesn't have to be passed down so many layers
        abstract_observables: list[AbstractObservable],
        observable_builder: ObservableBuilder,
        add_polygons: bool = False,
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
        detectors_walker.enter_node(self)

        if isinstance(self._layer, LayoutLayer):
            annotations = self.get_annotations(k)

            # circuit
            base_circuit = self._layer.to_circuit(
                k, reschedule_measurements=reschedule_measurements
            )
            annotations.circuit = base_circuit

            # detectors
            detectors_walker.visit_node(self)

            # observables
            if leaf_dict is not None:
                fns = leaf_dict.get(self)
                if fns is not None:
                    for fn, component in fns:
                        fn(self, component)

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

        if isinstance(self._layer, SequencedLayers):
            leaf_dict: dict[LayerNode, list[tuple[Callable, ObservableComponent]]] = {}

            if self in subtree_to_z:
                z = subtree_to_z[self]
                leaves = _get_ordered_leaves(self)

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
                        leaf_dict[leaves[-1]].append((ao_partial, ObservableComponent.REALIGNMENT))

                    if readout_layer not in leaf_dict:
                        leaf_dict[readout_layer] = []
                    leaf_dict[readout_layer].append((ao_partial, ObservableComponent.TOP_READOUTS))

            for child, next_child in itertools.pairwise(self._children):
                circ = child.generate_circuits_with_potential_polygons_stream(
                    k,
                    global_qubit_map,
                    reschedule_measurements,
                    detectors_walker,
                    subtree_to_z,
                    abstract_observables,
                    observable_builder,
                    add_polygons,
                    leaf_dict=leaf_dict,
                )

                if not next_child.is_repeated:
                    tick = stim.Circuit()
                    tick.append("TICK", [], [])
                    circ = itertools.chain(
                        circ, [tick]
                    )  # add TICK at the end if next child is not repeated

                yield from circ

            yield from self._children[-1].generate_circuits_with_potential_polygons_stream(
                k,
                global_qubit_map,
                reschedule_measurements,
                detectors_walker,
                subtree_to_z,
                abstract_observables,
                observable_builder,
                add_polygons,
                leaf_dict=leaf_dict,
            )

        if isinstance(self._layer, RepeatedLayer):
            body = self._children[0].generate_circuits_with_potential_polygons_stream(
                k,
                global_qubit_map,
                reschedule_measurements,
                detectors_walker,
                subtree_to_z,
                abstract_observables,
                observable_builder,
                add_polygons=add_polygons,
            )
            body_circuit = sum(
                (i for i in body if isinstance(i, stim.Circuit)),
                start=stim.Circuit(),
            )
            body_circuit.insert(0, stim.CircuitInstruction("TICK"))

            if add_polygons:
                yield from body  # only keep the first set of polygons

            yield body_circuit * self._layer.repetitions.integer_eval(k)

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
        circuits = self.generate_circuits_with_potential_polygons(
            k, global_qubit_map, add_polygons=False
        )
        ret = stim.Circuit()
        for circuit in circuits:
            assert isinstance(circuit, stim.Circuit)
            ret += circuit
        return ret

    def generate_circuit_stream(
        self,
        k: int,
        global_qubit_map: QubitMap,
        reschedule_measurements: bool,
        detectors_walker: AnnotateDetectorsOnLayerNode,
        subtree_to_z: dict[LayerNode, int],
        abstract_observables: list[AbstractObservable],
        observable_builder: ObservableBuilder,
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
        circuits = self.generate_circuits_with_potential_polygons_stream(
            k,
            global_qubit_map,
            reschedule_measurements,
            detectors_walker,
            subtree_to_z,
            abstract_observables,
            observable_builder,
            add_polygons=False,
        )

        # remove polygons from the stream and yield only circuits
        for item in circuits:
            if isinstance(item, stim.Circuit):
                yield item
