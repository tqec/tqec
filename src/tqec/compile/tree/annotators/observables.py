from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    ObservableBuilder,
    ObservableComponent,
)
from tqec.compile.tree.node import LayerNode, _annotate_observable_at_node, _get_ordered_leaves


def annotate_observable(
    root: LayerNode,
    k: int,
    observable: AbstractObservable,
    observable_index: int,
    observable_builder: ObservableBuilder,
) -> None:
    """Annotates the observables on the tree.

    Args:
        root: root node of the tree.
        k: distance parameter.
        observable: observable to annotate.
        observable_index: index of the observable in the circuit.
        observable_builder: builder that computes and constructs qubits whose
            measurements will be included in the logical observable.

    """
    for z, subtree_root in enumerate(root.children):
        leaves = _get_ordered_leaves(subtree_root)
        obs_slice = observable.slice_at_z(z)
        # Annotate the observable at the bottom of the blocks
        _annotate_observable_at_node(
            leaves[0],
            obs_slice,
            k,
            observable_index,
            observable_builder,
            ObservableComponent.BOTTOM_STABILIZERS,
        )
        readout_layer = leaves[-1]
        if obs_slice.temporal_hadamard_pipes:
            readout_layer = leaves[-2]
            # Annotate the observable at the realignment layer in temporal hadamard pipes
            _annotate_observable_at_node(
                leaves[-1],
                obs_slice,
                k,
                observable_index,
                observable_builder,
                ObservableComponent.REALIGNMENT,
            )
        # Annotate the observable at the top of the blocks
        _annotate_observable_at_node(
            readout_layer,
            obs_slice,
            k,
            observable_index,
            observable_builder,
            ObservableComponent.TOP_READOUTS,
        )
