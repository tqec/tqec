from typing_extensions import override
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import (
    compute_observable_qubits,
    get_observable_with_circuit,
)
from tqec.compile.tree.node import LayerNode, NodeWalkerInterface
from tqec.utils.exceptions import TQECException


class AnnotateObsOnLayerNode(NodeWalkerInterface):
    def __init__(
        self,
        k: int,
        observable: AbstractObservable,
        observable_index: int,
        max_z: int,
    ) -> None:
        self._k = k
        self._observable = observable
        self._observable_index = observable_index
        self._max_z = max_z
        # start from -1 because we need to walk the root node first
        self._current_z = -1

    @override
    def visit_node(self, node: LayerNode) -> None:
        if self._current_z < 0 or self._current_z > self._max_z:
            self._current_z += 1
            return

        first_leaf = node.get_first_leaf()
        last_leaf = node.get_last_leaf()

        for at_bottom, node in zip([True, False], [first_leaf, last_leaf]):
            assert isinstance(node._layer, LayoutLayer)
            annotations = node.get_annotations(self._k)
            if annotations.circuit is None:
                raise TQECException(
                    "Cannot annotate observables without the circuit annotation."
                )
            template, _ = node._layer.to_template_and_plaquettes()
            obs_qubits = compute_observable_qubits(
                self._k, self._observable, template, self._current_z, at_bottom
            )
            if obs_qubits:
                obs_annotation = get_observable_with_circuit(
                    annotations.circuit, self._observable_index, obs_qubits
                )
                annotations.observables.append(obs_annotation)
        self._current_z += 1
