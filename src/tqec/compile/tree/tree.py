from typing import Any, Mapping

import stim
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.tree.annotations import LayerTreeAnnotations
from tqec.compile.tree.annotators.circuit import AnnotateCircuitOnLayerNode
from tqec.compile.tree.annotators.detectors import AnnotateDetectorsOnLayerNode
from tqec.compile.tree.annotators.observables import annotate_observable
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.utils.exceptions import TQECException


class QubitLister(NodeWalker):
    def __init__(self, k: int):
        """Keeps in memory all the qubits used by the nodes explored.

        Args:
            k: scaling factor used to explore the quantum circuits.
        """
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
        """Returns all the qubits seen when exploring."""
        return self._seen_qubits


class LayerTree:
    def __init__(
        self,
        root: SequencedLayers,
        abstract_observables: list[AbstractObservable] | None = None,
        annotations: Mapping[int, LayerTreeAnnotations] | None = None,
    ):
        """Represents a computation as a tree.

        Note:
            It is expected that the root is a
            :class:`~tqec.compile.blocks.layer.composed.sequenced.SequencedLayers`
            with each of its children representing the computation on a timespan
            equivalent to the timespan of a cube.

        Args:
            root: root node of the tree.
            annotations: a mapping from positive integers representing the value
                of ``k``, the scaling factor, to annotations computed for that
                value of ``k``.
        """
        self._root = LayerNode(root)
        self._abstract_observables = abstract_observables or []
        self._annotations = dict(annotations) if annotations is not None else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self._root.to_dict(),
            "abstract_observables": self._abstract_observables,
            "annotations": {
                k: annotation.to_dict() for k, annotation in self._annotations.items()
            },
        }

    def _annotate_circuits(self, k: int) -> None:
        self._root.walk(AnnotateCircuitOnLayerNode(k))

    def _annotate_qubit_map(self, k: int) -> None:
        self._get_annotation(k).qubit_map = self._get_global_qubit_map(k)

    def _get_global_qubit_map(self, k: int) -> QubitMap:
        qubit_lister = QubitLister(k)
        self._root.walk(qubit_lister)
        return QubitMap.from_qubits(sorted(qubit_lister.seen_qubits))

    def _annotate_observables(self, k: int) -> None:
        for obs_idx, observable in enumerate(self._abstract_observables):
            annotate_observable(self._root, k, observable, obs_idx)

    def _annotate_detectors(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
    ) -> None:
        self._root.walk(
            AnnotateDetectorsOnLayerNode(
                k, manhattan_radius, detector_database, lookback
            )
        )

    def generate_circuit(
        self,
        k: int,
        include_qubit_coords: bool = True,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
    ) -> stim.Circuit:
        """Generate the quantum circuit representing ``self``.

        This method first annotates the tree according to the provided arguments
        and then use these annotations to generate the final quantum circuit.

        Args:
            k: scaling factor.
            include_qubit_coords: whether to include ``QUBIT_COORDS`` annotations
                in the returned quantum circuit or not. Default to ``True``.
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
            lookback: number of QEC rounds to consider to try to find detectors.
                Including more rounds increases computation time.

        Returns:
            a ``stim.Circuit`` instance implementing the computation described
            by ``self``.
        """
        self._annotate_circuits(k)
        self._annotate_qubit_map(k)
        self._annotate_detectors(k, manhattan_radius, detector_database, lookback)
        self._annotate_observables(k)
        annotations = self._get_annotation(k)
        assert annotations.qubit_map is not None

        circuit = stim.Circuit()
        if include_qubit_coords:
            circuit += annotations.qubit_map.to_circuit()
        circuit += self._root.generate_circuit(k, annotations.qubit_map)
        return circuit

    def _get_annotation(self, k: int) -> LayerTreeAnnotations:
        return self._annotations.setdefault(k, LayerTreeAnnotations())
