from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder
from tqec.blocks.layers.composed.base import BaseLayer
from tqec.plaquette.plaquette import Plaquettes
from tqec.scale import Scalable2D
from tqec.templates.indices.base import RectangularTemplate


@dataclass
class PlaquetteLayer(BaseLayer):
    template: RectangularTemplate
    plaquettes: Plaquettes

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        return self.template.scalable_shape

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> PlaquetteLayer:
        border_indices: set[int] = set()
        for border in borders:
            border_indices.update(
                self.template.get_border_indices(border.to_template_border())
            )
        return PlaquetteLayer(
            self.template, self.plaquettes.without_plaquettes(border_indices)
        )
