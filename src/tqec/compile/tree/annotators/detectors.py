from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import override

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.detectors.compute import compute_detectors_for_fixed_radius
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.tree.annotations import DetectorAnnotation
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import Template
from tqec.utils.exceptions import TQECError


@dataclass(frozen=True)
class LookbackInformation:
    """Stores data on one QEC round.

    This data-structure is used to store information that might be useful to
    compute detectors. It only represents one QEC round.

    Attributes:
        template: template representing the QEC round.
        plaquettes: plaquettes that can be used in conjunction with
            ``self.template`` to generate the quantum circuit representing the
            QEC round.
        measurement_records: all the measurement records of the QEC round
            represented by ``self``. This could in theory be computed from
            ``self.template`` and ``self.plaquettes`` by generating the quantum
            circuit and then extracting the measurement records from it, but it
            turns out that we already have access to these records when creating
            such a structure, so we store them to avoid re-computing.

    """

    template: Template
    plaquettes: Plaquettes
    measurement_records: MeasurementRecordsMap


@dataclass
class LookbackInformationList:
    """A sequence of :class:`LookbackInformation` instances."""

    infos: list[LookbackInformation] = field(default_factory=list)

    def append(
        self,
        template: Template,
        plaquettes: Plaquettes,
        measurement_records: MeasurementRecordsMap,
    ) -> None:
        """Add the provided parameters to the lookback window.

        This method might remove older items that should not be considered anymore from the lookback
        stack.
        """
        self.infos.append(LookbackInformation(template, plaquettes, measurement_records))

    def extend(self, other: LookbackInformationList, repetitions: int = 1) -> None:
        """Add the provided lookback information to self, potentially repeating it several times.

        This method can be used when exiting a REPEAT block to update the lookback information by
        taking into account that it might be repeated several times.

        """
        self.infos.extend(other.infos * repetitions)

    def __len__(self) -> int:
        return len(self.infos)

    def __getitem__(self, index: int | slice) -> LookbackInformation | list[LookbackInformation]:
        return self.infos[index]  # pragma: no cover


class LookbackStack:
    def __init__(self) -> None:
        """Initialise the lookback stack.

        The lookback stack can be used to query the current state for detector computation.

        This data-structure keeps information about the past QEC rounds in order to be able to query
        them and help in detector computation by only considering the ``N`` last rounds.

        In particular, this data-structure is useful to keep track of previous rounds in the
        presence of ``REPEAT`` blocks.

        """
        self._stack: list[LookbackInformationList] = [LookbackInformationList()]

    def enter_repeat_block(self) -> None:
        """Append a new entry to the stack."""
        self._stack.append(LookbackInformationList())

    def close_repeat_block(self, repetitions: int) -> None:
        """Remove the last entry on the stack, repeating it as needed into the new last entry."""
        if len(self._stack) < 2:
            raise TQECError(
                f"Only got {len(self._stack)} < 2 entries in the stack. That "
                "means that we are not in a REPEAT block. Cannot call "
                "close_repeat_block()."
            )
        self._stack[-2].extend(self._stack[-1], repetitions)
        self._stack.pop(-1)

    def append(
        self,
        template: Template,
        plaquettes: Plaquettes,
        measurement_records: MeasurementRecordsMap,
    ) -> None:
        """Append a new QEC round in the data-structure."""
        self._stack[-1].append(template, plaquettes, measurement_records)

    def _get_last_n(
        self, n: int
    ) -> tuple[list[Template], list[Plaquettes], list[MeasurementRecordsMap]]:
        if n < 0:
            raise TQECError(
                f"Cannot look back a negative number of rounds. Got a lookback value of {n}."
            )
        if n == 0:
            return [], [], []
        templates: list[Template] = []
        plaquettes: list[Plaquettes] = []
        measurement_records: list[MeasurementRecordsMap] = []
        # Filling the lists in reverse order (i.e., from earlier time to oldest
        # time) and correcting when returning.
        for element in reversed(self._stack):
            for info in reversed(element.infos):
                templates.append(info.template)
                plaquettes.append(info.plaquettes)
                measurement_records.append(info.measurement_records)
                if len(templates) == n:
                    return templates[::-1], plaquettes[::-1], measurement_records[::-1]

        return templates[::-1], plaquettes[::-1], measurement_records[::-1]

    def lookback(
        self,
        n: int,
    ) -> tuple[list[Template], list[Plaquettes], MeasurementRecordsMap]:
        """Get the last ``self._lookback`` QEC rounds."""
        templates, plaquettes, measurement_records = self._get_last_n(n)
        measurement_record = MeasurementRecordsMap()
        for mrec in measurement_records:
            measurement_record = measurement_record.with_added_measurements(mrec)
        return templates, plaquettes, measurement_record

    def __len__(self) -> int:
        if len(self._stack) > 1:
            raise TQECError(
                "Cannot get a meaningful stack length when a REPEAT block is in construction."
            )
        return len(self._stack[0])


class AnnotateDetectorsOnLayerNode(NodeWalker):
    def __init__(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        only_use_database: bool = False,
        lookback: int = 2,
        parallel_process_count: int = 1,
    ):
        """Walker computing and annotating detectors on leaf nodes.

        This class keeps track of the ``lookback`` previous leaf nodes seen and
        uses them to automatically compute the detectors at all the leaf nodes
        it encounters.

        Args:
            k: scaling factor.
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
            only_use_database: if ``True``, only detectors from the database will be
                used. An error will be raised if a situation that is not registered
                in the database is encountered. Default to ``False``.
            lookback: number of QEC rounds to consider to try to find detectors. Including more
                rounds increases computation time.
            parallel_process_count: number of processes to use for parallel processing.
                1 for sequential processing, >1 for parallel processing using
                ``parallel_process_count`` processes, and -1 for using all available
                CPU cores. Default to 1.

        """
        if lookback < 1:
            raise TQECError(
                "Cannot compute detectors without any layer. The `lookback` "
                f"parameter should be >= 1 but got {lookback}."
            )
        self._k = k
        self._manhattan_radius = manhattan_radius
        self._database = detector_database if detector_database is not None else DetectorDatabase()
        self._only_use_database = only_use_database
        self._lookback_size = lookback
        self._lookback_stack = LookbackStack()
        self._parallel_process_count = parallel_process_count

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not isinstance(node._layer, LayoutLayer):
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECError("Cannot compute detectors without the circuit annotation.")
        self._lookback_stack.append(
            *node._layer.to_template_and_plaquettes(),
            MeasurementRecordsMap.from_scheduled_circuit(annotations.circuit),
        )
        templates, plaquettes, measurement_records = self._lookback_stack.lookback(
            self._lookback_size
        )

        detectors = compute_detectors_for_fixed_radius(
            templates,
            self._k,
            plaquettes,
            self._manhattan_radius,
            self._database,
            self._only_use_database,
            self._parallel_process_count,
        )

        for detector in detectors:
            annotations.detectors.append(
                DetectorAnnotation.from_detector(detector, measurement_records)
            )

    @override
    def enter_node(self, node: LayerNode) -> None:
        if node.is_repeated:
            self._lookback_stack.enter_repeat_block()

    @override
    def exit_node(self, node: LayerNode) -> None:
        if not node.is_repeated:
            return
        # Note: this is the place to perform checks. In particular, checking that
        # detectors computed at the first repetition of the REPEAT block are also
        # valid at any repetitions. This is a requirement for the REPEAT block to
        # make sense, but that would be nice to include a check to avoid
        # misleadingly include detectors that are incorrect sometimes.
        repetitions = node.repetitions
        assert repetitions is not None
        self._lookback_stack.close_repeat_block(repetitions.integer_eval(self._k))
