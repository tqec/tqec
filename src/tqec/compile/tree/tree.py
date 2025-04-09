from typing import Any, Mapping

import stim
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.tree.annotations import LayerTreeAnnotations, Polygon
from tqec.compile.tree.annotators.circuit import AnnotateCircuitOnLayerNode
from tqec.compile.tree.annotators.detectors import AnnotateDetectorsOnLayerNode
from tqec.compile.tree.annotators.observables import annotate_observable
from tqec.compile.tree.annotators.polygons import AnnotatePolygonOnLayerNode
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.template import RPNGTemplate
from tqec.plaquette.rpng.visualisation import rpng_svg_viewer
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


class LayerVisualiser(NodeWalker):
    def __init__(self, k: int):
        super().__init__()
        self._k = k
        self._visualisations: list[str] = []

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not node.is_leaf:
            return
        layer = node._layer
        assert isinstance(layer, LayoutLayer)
        template, plaquettes = layer.to_template_and_plaquettes()
        rpngs = plaquettes.collection.map_values(
            lambda plaq: (
                plaq.debug_information.rpng
                if (
                    plaq.debug_information is not None
                    and plaq.debug_information.rpng is not None
                )
                else RPNGDescription.empty()
            )
        )
        rpng_template = RPNGTemplate(template, rpngs)
        rpng_instantiation = rpng_template.instantiate(self._k)
        self._visualisations.append(rpng_svg_viewer(rpng_instantiation))

    @property
    def visualisations(self) -> list[str]:
        return self._visualisations


class LayerTree:
    def __init__(
        self,
        root: SequencedLayers,
        observable_builder: ObservableBuilder,
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
            abstract_observables: a list of abstract observables to be compiled into
                observables. If set to ``None``, no observables will be compiled
                into the circuit.
            annotations: a mapping from positive integers representing the value
                of ``k``, the scaling factor, to annotations computed for that
                value of ``k``.
            observable_builder: the style of the surface code patch.

        """
        self._root = LayerNode(root)
        self._abstract_observables = abstract_observables or []
        self._annotations = dict(annotations) if annotations is not None else {}
        self._observable_builder = observable_builder

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
            annotate_observable(
                self._root, k, observable, obs_idx, self._observable_builder
            )

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

    def _annotate_polygons(
        self,
        k: int,
    ) -> None:
        self._root.walk(AnnotatePolygonOnLayerNode(k))

    def generate_crumble_url(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
        add_polygons: bool = True,
    ) -> str:
        """Generate the Crumble URL of the quantum circuit representing ``self``.

        This method first annotates the tree according to the provided arguments
        and then use these annotations to generate the final quantum circuit and
        convert it to a Crumble URL.

        Args:
            k: scaling factor.
            manhattan_radius: Parameter for the automatic computation of detectors.
                Should be large enough so that flows canceling each other to
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
            add_polygons: whether to include polygons in the Crumble URL. If
                ``True``, the polygons representing the stabilizers will be generated
                based on the RPNG information of underlying plaquettes and add
                to the Crumble URL.

        Returns:
            a string representing the Crumble URL of the quantum circuit.
        """
        if not add_polygons:
            circuit = self.generate_circuit(
                k,
                include_qubit_coords=True,
                manhattan_radius=manhattan_radius,
                detector_database=detector_database,
                lookback=lookback,
            )
            return str(circuit.to_crumble_url())
        self._generate_annotations(
            k, manhattan_radius, detector_database, lookback, add_polygons=True
        )
        annotations = self._get_annotation(k)
        qubit_map = annotations.qubit_map
        assert qubit_map is not None
        circuits_with_polygons = self._root.generate_circuits_with_potential_polygons(
            k, qubit_map, add_polygons=True
        )
        crumble_url: str = qubit_map.to_circuit().to_crumble_url() + ";"
        last_polygons: set[Polygon] = set()
        for item in circuits_with_polygons:
            if isinstance(item, stim.Circuit):
                circuit_crumble_url = item.to_crumble_url().replace(
                    "https://algassert.com/crumble#circuit=", ""
                )
                crumble_url += circuit_crumble_url
                crumble_url += ";"
            else:
                polygons = set(item)
                if polygons == last_polygons:
                    continue
                crumble_url += "".join(
                    polygon.to_crumble_url_string(qubit_map) for polygon in item
                )
                last_polygons = polygons
        return crumble_url

    def _generate_annotations(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
        add_polygons: bool = False,
    ) -> None:
        """Annotate the tree with circuits, qubit maps, detectors and observables."""
        self._annotate_circuits(k)
        self._annotate_qubit_map(k)
        self._annotate_detectors(k, manhattan_radius, detector_database, lookback)
        self._annotate_observables(k)
        if add_polygons:
            self._annotate_polygons(k)

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
                Should be large enough so that flows canceling each other to
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
        self._generate_annotations(
            k,
            manhattan_radius,
            detector_database,
            lookback,
        )
        annotations = self._get_annotation(k)
        assert annotations.qubit_map is not None

        circuit = stim.Circuit()
        if include_qubit_coords:
            circuit += annotations.qubit_map.to_circuit()
        circuit += self._root.generate_circuit(k, annotations.qubit_map)
        return circuit

    def _get_annotation(self, k: int) -> LayerTreeAnnotations:
        return self._annotations.setdefault(k, LayerTreeAnnotations())

    def layers_to_svg(self, k: int) -> list[str]:
        visualiser = LayerVisualiser(k)
        self._root.walk(visualiser)
        return visualiser.visualisations
