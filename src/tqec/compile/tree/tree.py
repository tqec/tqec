from typing import Any, Mapping

import stim
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.tree.annotations import LayerTreeAnnotations
from tqec.compile.tree.annotators.circuit import AnnotateCircuitOnLayoutNode
from tqec.compile.tree.node import LayerNode, NodeWalkerInterface
from tqec.utils.exceptions import TQECException


class _QubitListerExplorator(NodeWalkerInterface):
    def __init__(self, k: int):
        super().__init__()
        self._k = k
        self._seen_qubits: set[GridQubit] = set()

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not node.is_leaf:
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECException("Cannot list qubits without the circuit annotation.")
        self._seen_qubits |= annotations.circuit.qubits

    @property
    def seen_qubits(self) -> set[GridQubit]:
        return self._seen_qubits


class LayerTree:
    def __init__(
        self,
        root: SequencedLayers,
        annotations: Mapping[int, LayerTreeAnnotations] | None = None,
    ):
        self._root = LayerNode(root)
        self._annotations = dict(annotations) if annotations is not None else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self._root.to_dict(),
            "annotations": {
                k: annotation.to_dict() for k, annotation in self._annotations.items()
            },
        }

    def _annotate_circuits(self, k: int) -> None:
        self._root.walk(AnnotateCircuitOnLayoutNode(k))

    def _annotate_qubit_map(self, k: int) -> None:
        self._get_annotation(k).qubit_map = self._get_global_qubit_map(k)

    def _get_global_qubit_map(self, k: int) -> QubitMap:
        qubit_lister = _QubitListerExplorator(k)
        self._root.walk(qubit_lister)
        return QubitMap.from_qubits(sorted(qubit_lister.seen_qubits))

    def _annotate_observable(self, observable: AbstractObservable) -> None:
        pass

    def _annotate_detectors(
        self,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
    ) -> None:
        pass

    def generate_circuit(
        self, k: int, include_qubit_coords: bool = True
    ) -> stim.Circuit:
        self._annotate_circuits(k)
        self._annotate_qubit_map(k)
        self._annotate_detectors(k)
        annotations = self._get_annotation(k)
        if not annotations.has_qubit_map:
            raise TQECException(
                "Cannot generate the final quantum circuit before calling "
                "LayerTree.annotate_qubit_map."
            )
        assert annotations.qubit_map is not None
        circuit = stim.Circuit()
        if include_qubit_coords:
            circuit += annotations.qubit_map.to_circuit()
        circuit += self._root.generate_circuit(k, annotations.qubit_map)
        return circuit

    def _get_annotation(self, k: int) -> LayerTreeAnnotations:
        return self._annotations.setdefault(k, LayerTreeAnnotations())
