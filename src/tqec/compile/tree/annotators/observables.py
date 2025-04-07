from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.compile import PatchStyle
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    compute_observable_qubits,
    get_observable_with_circuit,
)
from tqec.compile.tree.node import LayerNode
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
    for z, subtree_root in enumerate(root.children):
        first_leaf = _get_first_leaf(subtree_root)
        last_leaf = _get_last_leaf(subtree_root)
        for at_bottom, node in zip([True, False], [first_leaf, last_leaf]):
            assert isinstance(node._layer, LayoutLayer)
            annotations = node.get_annotations(k)
            if annotations.circuit is None:
                raise TQECException(
                    "Cannot annotate observables without the circuit annotation."
                )
            template, _ = node._layer.to_template_and_plaquettes()
            obs_qubits = compute_observable_qubits(
                k, observable, template, z, at_bottom, patch_style
            )
            if obs_qubits:
                obs_annotation = get_observable_with_circuit(
                    annotations.circuit, observable_index, obs_qubits
                )
                annotations.observables.append(obs_annotation)
