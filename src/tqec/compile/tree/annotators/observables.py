from __future__ import annotations

from typing import TYPE_CHECKING

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    Observable,
    ObservableBuilder,
    ObservableComponent,
    get_observable_with_measurement_records,
)

if TYPE_CHECKING:
    from tqec.compile.tree.node import LayerNode


def get_ordered_leaves(root: LayerNode) -> list[LayerNode]:
    """Return the leaves of the tree in time order."""
    if root.is_leaf:
        return [root]
    return [n for child in root.children for n in get_ordered_leaves(child)]


def resolve_observable_measurements(
    root: LayerNode,
    k: int,
    observable: AbstractObservable,
    observable_index: int,
    observable_builder: ObservableBuilder,
    slices_with_temporal_hadamard_layer: set[int],
) -> list[tuple[LayerNode, Observable]]:
    """Resolve observable measurement support using the same binding as emission.

    Args:
        root: root node of the tree.
        k: distance parameter.
        observable: observable to annotate.
        observable_index: index of the observable in the circuit.
        observable_builder: builder that computes and constructs qubits whose
            measurements will be included in the logical observable.
        slices_with_temporal_hadamard_layer: z slices containing a temporal
            Hadamard layer.

    """
    resolved: list[tuple[LayerNode, Observable]] = []
    for z, subtree_root in enumerate(root.children):
        obs_slice = observable.slice_at_z(z)
        for node, component in _observable_components_at_slice(
            subtree_root, obs_slice, z in slices_with_temporal_hadamard_layer
        ):
            annotation = _resolve_observable_at_node(
                node, obs_slice, k, observable_index, observable_builder, component
            )
            if annotation is not None:
                resolved.append((node, annotation))
    return resolved


def _observable_components_at_slice(
    root: LayerNode, obs_slice: AbstractObservable, has_temporal_hadamard: bool
) -> list[tuple[LayerNode, ObservableComponent]]:
    """Select binding layers identically for streamed emission and internal semantics."""
    leaves = get_ordered_leaves(root)
    components = [(leaves[0], ObservableComponent.BOTTOM_STABILIZERS)]
    if has_temporal_hadamard and obs_slice.temporal_hadamard_pipes:
        components.append((leaves[-1], ObservableComponent.REALIGNMENT))
    components.append(
        (
            leaves[-2] if has_temporal_hadamard else leaves[-1],
            ObservableComponent.TOP_READOUTS,
        )
    )
    return components


def _resolve_observable_at_node(
    node: LayerNode,
    obs_slice: AbstractObservable,
    k: int,
    observable_index: int,
    observable_builder: ObservableBuilder,
    component: ObservableComponent,
) -> Observable | None:
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
        return obs_annotation
    return None


def annotate_observable(
    root: LayerNode,
    k: int,
    observable: AbstractObservable,
    observable_index: int,
    observable_builder: ObservableBuilder,
    slices_with_temporal_hadamard_layer: set[int],
) -> None:
    """Emit the measurement support produced by the shared resolver."""
    for node, annotation in resolve_observable_measurements(
        root,
        k,
        observable,
        observable_index,
        observable_builder,
        slices_with_temporal_hadamard_layer,
    ):
        node.get_annotations(k).observables.append(annotation)


def _annotate_observable_at_node(
    node: LayerNode,
    obs_slice: AbstractObservable,
    k: int,
    observable_index: int,
    observable_builder: ObservableBuilder,
    component: ObservableComponent,
) -> None:
    annotation = _resolve_observable_at_node(
        node, obs_slice, k, observable_index, observable_builder, component
    )
    if annotation is not None:
        node.get_annotations(k).observables.append(annotation)
