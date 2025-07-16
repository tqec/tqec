from typing_extensions import override

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.tree.node import LayerNode, NodeWalker


class AnnotateCircuitOnLayerNode(NodeWalker):
    def __init__(self, k: int):
        """Walker annotating ``stim.Circuit`` instances implementing the node on each leaf node.

        Args:
            k: scaling factor.

        """
        self._k = k

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not node.is_leaf:
            return
        assert isinstance(node._layer, LayoutLayer)
        node.set_circuit_annotation(self._k, node._layer.to_circuit(self._k))
