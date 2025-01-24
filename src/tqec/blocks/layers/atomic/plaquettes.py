from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.layers.composed.base import BaseLayer
from tqec.circuit.generation import generate_circuit
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.plaquette import Plaquettes
from tqec.scale import Scalable2D
from tqec.templates.indices.base import RectangularTemplate
from tqec.templates.indices.enums import TemplateBorder


@dataclass
class PlaquetteLayer(BaseLayer):
    template: RectangularTemplate
    plaquettes: Plaquettes

    @override
    def to_circuit(self, k: int) -> ScheduledCircuit:
        return generate_circuit(self.template, k, self.plaquettes)

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        return self.template.scalable_shape

    @override
    def with_borders_trimed(self, borders: Iterable[TemplateBorder]) -> PlaquetteLayer:
        border_indices: set[int] = set()
        for border in borders:
            border_indices.update(self.template.get_border_indices(border))
        return PlaquetteLayer(
            self.template, self.plaquettes.without_plaquettes(border_indices)
        )
