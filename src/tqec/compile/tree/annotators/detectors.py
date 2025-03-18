from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from typing_extensions import override

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.detectors.compute import compute_detectors_for_fixed_radius
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.tree.annotations import DetectorAnnotation
from tqec.compile.tree.node import LayerNode, NodeWalker
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import Template
from tqec.utils.exceptions import TQECException

T = TypeVar("T")


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
class LookbackInformations:
    """A sequence of :class:`LookbackInformation` instances."""

    infos: list[LookbackInformation] = field(default_factory=list)

    def append(
        self,
        template: Template,
        plaquettes: Plaquettes,
        measurement_records: MeasurementRecordsMap,
    ) -> None:
        """Add the provided parameters to the lookback window, potentially removing
        older items that should not be considered anymore."""
        self.infos.append(
            LookbackInformation(template, plaquettes, measurement_records)
        )

    def extend(self, other: LookbackInformations, repetitions: int = 1) -> None:
        self.infos.extend(other.infos * repetitions)

    def __len__(self) -> int:
        return len(self.infos)

    def __getitem__(
        self, index: int | slice
    ) -> LookbackInformation | list[LookbackInformation]:
        return self.infos[index]


class LookbackStack:
    def __init__(self, lookback: int) -> None:
        """Initialise the lookback stack that can be used to query the current
        state for detector computation.

        This data-structure keeps information about the past QEC rounds in order
        to be able to query them and help in detector computation by only
        considering the ``N`` last rounds.

        In particular, this data-structure is useful to keep track of previous
        rounds in the presence of ``REPEAT`` blocks.

        Args:
            lookback: the number of QEC rounds that should be used to compute
                detectors.
        """
        self._lookback = lookback
        self._stack: list[LookbackInformations] = [LookbackInformations()]

    def enter_repeat_block(self) -> None:
        self._stack.append(LookbackInformations())

    def close_repeat_block(self, repetitions: int) -> None:
        if len(self._stack) < 2:
            raise TQECException(
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

    def get_current_lookback(
        self,
    ) -> tuple[list[Template], list[Plaquettes], MeasurementRecordsMap]:
        """Get the last ``self._lookback`` QEC rounds."""
        templates, plaquettes, measurement_records = self._get_last_n(self._lookback)
        measurement_record = measurement_records[0]
        for mrec in measurement_records[1:]:
            measurement_record = measurement_record.with_added_measurements(mrec)
        return templates, plaquettes, measurement_record


class AnnotateDetectorsOnLayerNode(NodeWalker):
    def __init__(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
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
            lookback: number of QEC rounds to consider to try to find detectors.
                Including more rounds increases computation time. Cannot be over
                ``2`` for the moment.
        """
        if lookback < 1:
            raise TQECException(
                "Cannot compute detectors without any layer. The `lookback` "
                f"parameter should be >= 1 but got {lookback}."
            )
        if lookback > 2:
            raise TQECException(
                "Cannot annotate detectors by considering more than 2 QEC rounds "
                "at the moment."
            )
        self._k = k
        self._manhattan_radius = manhattan_radius
        self._database = detector_database or DetectorDatabase()
        self._lookback_stack = LookbackStack(lookback)

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not isinstance(node._layer, LayoutLayer):
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECException(
                "Cannot compute detectors without the circuit annotation."
            )
        self._lookback_stack.append(
            *node._layer.to_template_and_plaquettes(),
            MeasurementRecordsMap.from_scheduled_circuit(annotations.circuit),
        )
        templates, plaquettes, measurement_records = (
            self._lookback_stack.get_current_lookback()
        )

        detectors = compute_detectors_for_fixed_radius(
            templates, self._k, plaquettes, self._manhattan_radius, self._database
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
