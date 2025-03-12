from typing import MutableSequence, TypeVar

from typing_extensions import override

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.detectors.compute import compute_detectors_for_fixed_radius
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.tree.annotations import DetectorAnnotation
from tqec.compile.tree.node import LayerNode, NodeWalkerInterface
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import Template
from tqec.utils.exceptions import TQECException

T = TypeVar("T")


def _append_with_capped_size(seq: MutableSequence[T], obj: T, lookback: int) -> None:
    seq.append(obj)
    if len(seq) > lookback:
        seq.pop(0)


class AnnotateDetectorsOnLayoutNode(NodeWalkerInterface):
    def __init__(
        self,
        k: int,
        manhattan_radius: int = 2,
        detector_database: DetectorDatabase | None = None,
        lookback: int = 2,
    ):
        self._k = k
        self._manhattan_radius = manhattan_radius
        self._database = detector_database or DetectorDatabase()
        self._lookback = lookback
        self._previous_templates: list[Template] = []
        self._previous_plaquettes: list[Plaquettes] = []
        self._measurement_records: list[MeasurementRecordsMap] = []

    def append(
        self,
        template: Template,
        plaquettes: Plaquettes,
        measurement_records: MeasurementRecordsMap,
    ) -> None:
        _append_with_capped_size(self._previous_templates, template, self._lookback)
        _append_with_capped_size(self._previous_plaquettes, plaquettes, self._lookback)
        _append_with_capped_size(
            self._measurement_records, measurement_records, self._lookback
        )

    @property
    def full_lookback_measurement_record(self) -> MeasurementRecordsMap:
        ret = MeasurementRecordsMap()
        for mrecords in self._measurement_records:
            ret = ret.with_added_measurements(mrecords)
        return ret

    @override
    def visit_node(self, node: LayerNode) -> None:
        if not isinstance(node._layer, LayoutLayer):
            return
        annotations = node.get_annotations(self._k)
        if annotations.circuit is None:
            raise TQECException(
                "Cannot compute detectors without the circuit annotation."
            )
        template, plaquettes = node._layer.to_template_and_plaquettes()
        self.append(
            template,
            plaquettes,
            MeasurementRecordsMap.from_scheduled_circuit(annotations.circuit),
        )
        detectors = compute_detectors_for_fixed_radius(
            self._previous_templates,
            self._k,
            self._previous_plaquettes,
            self._manhattan_radius,
            self._database,
        )
        measurement_records = self.full_lookback_measurement_record
        for detector in detectors:
            annotations.detectors.append(
                DetectorAnnotation.from_detector(detector, measurement_records)
            )
