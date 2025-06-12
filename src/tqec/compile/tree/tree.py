from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping
import warnings

import stim
import svg
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
from tqec.utils.exceptions import TQECException
from tqec.utils.paths import DEFAULT_DETECTOR_DATABASE_PATH
from tqec.visualisation.computation.plaquette.grid import plaquette_grid_svg_viewer


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
    def __init__(
        self,
        k: int,
        errors: Sequence[stim.ExplainedError] = tuple(),
        font_size: float = 0.5,
        font_color: str = "red",
    ):
        super().__init__()
        self._k = k
        self._svgs_stack: list[list[svg.SVG]] = [list()]
        self._num_tick_stack: list[list[int]] = [list()]
        self._errors: list[stim.ExplainedError] = list(errors)
        self._font_size = font_size
        self._font_color = font_color

    @override
    def enter_node(self, node: LayerNode) -> None:
        if node.is_repeated:
            self._svgs_stack.append(list())
            self._num_tick_stack.append(list())

    @override
    def exit_node(self, node: LayerNode) -> None:
        if not node.is_repeated:
            return
        if len(self._svgs_stack) < 2:
            raise TQECException(
                "Logical error: exiting a repeated node with less than 2 entries in the stack."
            )
        assert node.repetitions is not None
        repetitions = node.repetitions.integer_eval(self._k)
        self._svgs_stack[-2].extend(self._svgs_stack.pop(-1) * repetitions)
        self._num_tick_stack[-2].extend(self._num_tick_stack.pop(-1) * repetitions)

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not node.is_leaf:
            return
        layer = node._layer
        assert isinstance(layer, LayoutLayer)
        template, plaquettes = layer.to_template_and_plaquettes()
        instantiation = template.instantiate_list(self._k)
        drawers = plaquettes.collection.map_values(
            lambda plaq: plaq.debug_information.get_svg_drawer()
        )
        self._svgs_stack[-1].append(
            plaquette_grid_svg_viewer(instantiation, drawers, errors=self._errors)
        )
        self._num_tick_stack[-1].append(layer.timesteps(self._k))

    def get_tick_text(self, start: int, end: int) -> svg.Text:
        return svg.Text(
            x=0,
            y=0,
            fill=self._font_color,
            font_size=self._font_size,
            text_anchor="start",
            dominant_baseline="hanging",
            text=f"TICKs: {start} -> {end}",
        )

    def _get_errors_within(self, start: int, end: int) -> list[stim.ExplainedError]:
        return [
            err
            for err in self._errors
            if (start <= err.circuit_error_locations[0].tick_offset < end)
        ]

    @property
    def visualisations(self) -> list[str]:
        if len(self._svgs_stack) > 1:
            warnings.warn(
                "Trying to get the layer visualisations but the stack contains more than one "
                "element. You may get incorrect results. Did you forget to close a REPEAT block?"
            )
        ret: list[str] = []
        current_tick: int = 0
        for s, t in zip(self._svgs_stack[0], self._num_tick_stack[0]):
            next_tick = current_tick + t
            # Adding text to mark which TICKs are concerned.
            assert s.elements is not None
            s.elements.append(self.get_tick_text(current_tick, next_tick))
            ret.append(s.as_str())
        return ret


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
        database_path: Path = DEFAULT_DETECTOR_DATABASE_PATH,
        only_use_database: bool = False,
        lookback: int = 2,
    ) -> None:
        if manhattan_radius <= 0:
            return
        self._root.walk(
            AnnotateDetectorsOnLayerNode(
                k, manhattan_radius, detector_database, only_use_database, lookback
            )
        )
        # The database will have been updated inside the above function, and here at
        # the end of the computation we save it to file:
        if detector_database is not None:
            detector_database.to_file(database_path)

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
            k, manhattan_radius, detector_database, lookback=lookback, add_polygons=True
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
        database_path: Path = DEFAULT_DETECTOR_DATABASE_PATH,
        only_use_database: bool = False,
        lookback: int = 2,
        add_polygons: bool = False,
    ) -> None:
        """Annotate the tree with circuits, qubit maps, detectors and observables."""
        self._annotate_circuits(k)
        self._annotate_qubit_map(k)
        # This method will also update the detector_database and save it to disk at database_path.
        self._annotate_detectors(
            k,
            manhattan_radius,
            detector_database,
            database_path,
            only_use_database,
            lookback,
        )
        self._annotate_observables(k)
        if add_polygons:
            self._annotate_polygons(k)

    def generate_circuit(
        self,
        k: int,
        include_qubit_coords: bool = True,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        database_path: str | Path = DEFAULT_DETECTOR_DATABASE_PATH,
        do_not_use_database: bool = False,
        only_use_database: bool = False,
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
            detector_database: an instance to retrieve from / store in detectors
                that are computed as part of the circuit generation. If not given,
                the detectors are retrieved from/stored in the the provided
                ``database_path``.
            database_path: specify where to save to after the calculation.
                This defaults to :data:`.DEFAULT_DETECTOR_DATABASE_PATH` if
                not specified. If detector_database is not passed in, the code attempts to
                retrieve the database from this location.
            do_not_use_database: if ``True``, even the default database will not be used.
            only_use_database: if ``True``, only detectors from the database
                will be used. An error will be raised if a situation that is not
                registered in the database is encountered.
            lookback: number of QEC rounds to consider to try to find detectors.
                Including more rounds increases computation time.

        Returns:
            a ``stim.Circuit`` instance implementing the computation described
            by ``self``.
        """
        # First, before we start any computations, decide which detector database to use.
        if isinstance(database_path, str):
            database_path = Path(database_path)
        # If the user has passed a database in, use that, otherwise:
        if detector_database is None:  # Nothing passed in,
            if database_path.exists():  # look for an existing database at the path.
                detector_database = DetectorDatabase.from_file(database_path)
            else:  # if there is no existing database, create one.
                detector_database = DetectorDatabase()
        # If do_not_use_database is True, override the above code and reset the database to None
        if do_not_use_database:
            detector_database = None

        self._generate_annotations(
            k,
            manhattan_radius,
            detector_database=detector_database,
            database_path=database_path,
            only_use_database=only_use_database,
            lookback=lookback,
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

    def layers_to_svg(
        self, k: int, errors: Sequence[stim.ExplainedError] = tuple()
    ) -> list[str]:
        visualiser = LayerVisualiser(k, errors)
        self._root.walk(visualiser)
        return visualiser.visualisations
