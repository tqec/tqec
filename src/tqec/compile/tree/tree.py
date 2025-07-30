from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any

import stim
from typing_extensions import override

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.detectors.database import CURRENT_DATABASE_VERSION, DetectorDatabase
from tqec.compile.observables.abstract_observable import AbstractObservable
from tqec.compile.observables.builder import ObservableBuilder
from tqec.compile.tree.annotations import LayerTreeAnnotations, Polygon
from tqec.compile.tree.annotators.circuit import AnnotateCircuitOnLayerNode
from tqec.compile.tree.annotators.detectors import AnnotateDetectorsOnLayerNode
from tqec.compile.tree.annotators.observables import annotate_observable
from tqec.compile.tree.annotators.polygons import AnnotatePolygonOnLayerNode
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.post_processing.shift import shift_to_only_positive
from tqec.utils.exceptions import TQECError, TQECWarning
from tqec.utils.paths import DEFAULT_DETECTOR_DATABASE_PATH
from tqec.visualisation.computation.tree import LayerVisualiser


class QubitLister(NodeWalker):
    def __init__(self, k: int):
        """Keep in memory all the qubits used by the nodes explored.

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
            raise TQECError("Cannot list qubits without the circuit annotation.")
        self._seen_qubits |= annotations.circuit.qubits

    @property
    def seen_qubits(self) -> set[GridQubit]:
        """Return all the qubits seen when exploring."""
        return self._seen_qubits


class LayerTree:
    def __init__(
        self,
        root: SequencedLayers,
        observable_builder: ObservableBuilder,
        abstract_observables: list[AbstractObservable] | None = None,
        annotations: Mapping[int, LayerTreeAnnotations] | None = None,
    ):
        """Represent a computation as a tree.

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
        """Return a dictionary representation of ``self``."""
        return {  # pragma: no cover
            "root": self._root.to_dict(),
            "abstract_observables": self._abstract_observables,
            "annotations": {k: annotation.to_dict() for k, annotation in self._annotations.items()},
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
            annotate_observable(self._root, k, observable, obs_idx, self._observable_builder)

    def _annotate_detectors(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        database_path: Path = DEFAULT_DETECTOR_DATABASE_PATH,
        only_use_database: bool = False,
        lookback: int = 2,
        parallel_process_count: int = 1,
    ) -> None:
        if manhattan_radius <= 0:
            return  # pragma: no cover
        self._root.walk(
            AnnotateDetectorsOnLayerNode(
                k,
                manhattan_radius,
                detector_database,
                only_use_database,
                lookback,
                parallel_process_count,
            )
        )
        # The database will have been updated inside the above function, and here at
        # the end of the computation we save it to file.
        if detector_database is not None:
            detector_database.to_file(database_path)

    def _annotate_polygons(
        self,
        k: int,
    ) -> None:
        self._root.walk(AnnotatePolygonOnLayerNode(k))  # pragma: no cover

    def generate_crumble_url(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
        add_polygons: bool = True,
        shift_to_positive: bool = True,
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
            shift_to_positive: if ``True``, the resulting circuit is shifted such
                that only qubits with positive coordinates are used. Else, the
                circuit is left as is.

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
        self._generate_annotations(k, manhattan_radius, detector_database, lookback=lookback)
        self._annotate_polygons(k)
        annotations = self._get_annotation(k)
        qubit_map = annotations.qubit_map
        assert qubit_map is not None
        circuits_with_polygons = self._root.generate_circuits_with_potential_polygons(
            k, qubit_map, add_polygons=True
        )
        qubit_map_circuit = qubit_map.to_circuit()
        if shift_to_positive:
            qubit_map_circuit = shift_to_only_positive(qubit_map_circuit)
        crumble_url: str = qubit_map_circuit.to_crumble_url() + ";"
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
                crumble_url += "".join(polygon.to_crumble_url_string(qubit_map) for polygon in item)
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
        parallel_process_count: int = 1,
    ) -> None:
        """Annotate the tree with circuits, qubit maps, detectors and observables."""
        # If already annotated, no need to re-annotate.
        if k in self._annotations:
            return  # pragma: no cover
        # Else, perform all the needed computations.
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
            parallel_process_count,
        )
        self._annotate_observables(k)

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
                the detectors are retrieved from/stored in the provided
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
        # We need to know for later if the user explicitly provided a database or
        # not to decide if we should warn or raise.
        user_defined = (
            detector_database is not None or database_path != DEFAULT_DETECTOR_DATABASE_PATH
        )
        # If the user has passed a database in, use that, otherwise:
        if detector_database is None:  # Nothing passed in,
            if database_path.exists():  # look for an existing database at the path.
                detector_database = DetectorDatabase.from_file(database_path)
            else:  # if there is no existing database, create one.
                detector_database = DetectorDatabase()
        # If do_not_use_database is True, override the above code and reset the database to None
        if do_not_use_database:
            detector_database = None
        if detector_database is not None:
            loaded_version = detector_database.version
            current_version = CURRENT_DATABASE_VERSION
            if loaded_version != current_version:
                if user_defined:
                    raise TQECError(
                        f"The detector database on disk you have specified is incompatible with"
                        f" the version in the TQEC code you are running. The version of the disk"
                        f" database is {loaded_version}, while the version in the TQEC code is "
                        f"{current_version}."
                    )
                else:  # ie using the default
                    warnings.warn(
                        f"The default detector database that you have saved on your system is out "
                        f"of date (version {loaded_version}). The version in the TQEC code you are "
                        f"running is newer (version {current_version}). The database will be "
                        "regenerated.",
                        TQECWarning,
                    )
                    detector_database = DetectorDatabase()

        # Enable parallel processing only if the detector database is empty or None,
        # as current parallelization is effective only in this case.
        # If we later support efficient parallelism with a populated database,
        # we will expose the parallel_count parameter to users.
        parallel_process_count = (
            cpu_count() // 2 + 1
            if (detector_database is None or len(detector_database) == 0)
            else 1
        )

        self._generate_annotations(
            k,
            manhattan_radius,
            detector_database=detector_database,
            database_path=database_path,
            only_use_database=only_use_database,
            lookback=lookback,
            parallel_process_count=parallel_process_count,
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
        self,
        k: int,
        errors: Sequence[stim.ExplainedError] = tuple(),
        show_observable: int | None = None,
    ) -> list[str]:
        """Visualize the layers as a list of SVG strings.

        Args:
            k: scaling factor.
            errors: a sequence of errors to be drawn on the layers. Each error
                is visualised with a cross. The cross colour follows the XYZ=RGB
                convention, and the moment index at which the error takes place
                is written above the cross (an error is always scheduled at the
                end of the moment, so any operation applied at the same moment
                is applied before the error).
            show_observable: the index of the observable to be drawn on the layers.
                If set to ``None``, no observable will be shown. If set to an
                integer, the observable with that index will be shown. The
                observable is represented as the set of included measurements.
                A yellow star on the plaquette vertex indicates a data qubit
                readout, while a star on the plaquette face indicates a
                stabilizer measurements.

        Returns:
            a list of SVG strings representing the layers of the tree.

        """
        if show_observable is not None and show_observable >= len(self._abstract_observables):
            raise TQECError(
                f"{show_observable:=} is out of range for the number of "
                f"abstract observables ({len(self._abstract_observables)})."
            )
        annotations = self._annotations.get(k, LayerTreeAnnotations())
        tl, br = (
            annotations.qubit_map.qubit_bounds()
            if annotations.qubit_map is not None
            else (None, None)
        )
        # Note: if the top-left and bottom-right qubits are not None, we just computed them from
        # the resulting circuit. We want to stick to the regular plaquette grid, and that might not
        # be the case here because boundary plaquettes might not use the extremal data-qubits.
        # As data-qubits are located on odd coordinates, we just ensure that the boundary
        # coordinates are odd, flooring or ceiling to the closest odd coordinates depending on the
        # boundary to make sure we extended the viewport (and not reduce it).
        if tl is not None:
            tl = GridQubit(tl.x - 1 if tl.x % 2 == 0 else tl.x, tl.y - 1 if tl.y % 2 == 0 else tl.y)
        if br is not None:
            br = GridQubit(br.x + 1 if br.x % 2 == 0 else br.x, br.y + 1 if br.y % 2 == 0 else br.y)
        visualiser = LayerVisualiser(
            k, errors, show_observable, top_left_qubit=tl, bottom_right_qubit=br
        )
        self._root.walk(visualiser)
        return visualiser.visualisations
