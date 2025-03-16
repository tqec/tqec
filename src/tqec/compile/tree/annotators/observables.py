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
        order_to_z: dict[int, int],
        bottom_orders: set[int],
        top_orders: set[int],
    ) -> None:
        self._k = k
        self._observable = observable
        self._observable_index = observable_index
        self._o2z = order_to_z
        assert bottom_orders.isdisjoint(
            top_orders
        ), "Bottom and top layers should not overlap."
        self._bottom_orders = bottom_orders
        self._top_orders = top_orders

    @override
    def visit_node(self, node: LayerNode) -> None:
        # Only annotate leaf nodes
        if not isinstance(node._layer, LayoutLayer):
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECException(
                "Cannot annotate observables without the circuit annotation."
            )
        order = node.order
        assert order is not None, "Leaf nodes should have an order assigned."
        z = self._o2z[order]
        # Only annotate the first or last leaf node
        at_bottom = order in self._bottom_orders
        at_top = order in self._top_orders
        if not at_bottom and not at_top:
            return
        template, _ = node._layer.to_template_and_plaquettes()
        obs_qubits = compute_observable_qubits(
            self._k, self._observable, template, z, at_bottom
        )
        if not obs_qubits:
            return
        obs_annotation = get_observable_with_circuit(
            annotations.circuit, self._observable_index, obs_qubits
        )
        annotations.observables.append(obs_annotation)
