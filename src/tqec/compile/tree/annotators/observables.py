from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    compute_observable_qubits,
    get_observable_with_measurement_records,
)
from tqec.compile.tree.node import LayerNode
from tqec.utils.enums import PatchStyle
from tqec.utils.exceptions import TQECException


def _get_first_leaf(root: LayerNode) -> LayerNode:
    """Returns the first leaf node in the tree."""
    if root.is_leaf:
        return root
    return _get_first_leaf(root._children[0])


def _get_last_leaf(root: LayerNode) -> LayerNode:
    """Returns the last leaf node in the tree."""
    if root.is_leaf:
        return root
    return _get_last_leaf(root._children[-1])


def annotate_observable(
    root: LayerNode,
    k: int,
    observable: AbstractObservable,
    observable_index: int,
    patch_style: PatchStyle,
) -> None:
    """Annotates the observables on the tree.

    Args:
        root: root node of the tree.
        k: distance parameter.
        observable: observable to annotate.
        observable_index: index of the observable in the circuit.
        patch_style: style of the surface code patch to be used during compilation.
    """
    from tqec.compile.observables.fixed_parity_builder import (
        FIXED_PARITY_OBSERVABLE_BUILDER,
    )
    from tqec.compile.observables.fixed_bulk_builder import (
        FIXED_BULK_OBSERVABLE_BUILDER,
    )

    obs_builder = (
        FIXED_PARITY_OBSERVABLE_BUILDER
        if patch_style == PatchStyle.FixedBoundaryParity
        else FIXED_BULK_OBSERVABLE_BUILDER
    )

    for z, subtree_root in enumerate(root.children):
        first_leaf = _get_first_leaf(subtree_root)
        last_leaf = _get_last_leaf(subtree_root)
        obs_slice = observable.slice_at_z(z)
        for at_bottom, node in zip([True, False], [first_leaf, last_leaf]):
            assert isinstance(node._layer, LayoutLayer)
            annotations = node.get_annotations(k)
            if annotations.circuit is None:
                raise TQECException(
                    "Cannot annotate observables without the circuit annotation."
                )
            template, _ = node._layer.to_template_and_plaquettes()
            obs_qubits = compute_observable_qubits(
                k, obs_slice, template, at_bottom, obs_builder
            )
            if obs_qubits:
                measurement_record = MeasurementRecordsMap.from_scheduled_circuit(
                    annotations.circuit
                )
                obs_annotation = get_observable_with_measurement_records(
                    obs_qubits, measurement_record, observable_index
                )
                annotations.observables.append(obs_annotation)
