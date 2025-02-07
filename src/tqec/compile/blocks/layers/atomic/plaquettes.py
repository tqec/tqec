from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import RectangularTemplate
from tqec.utils.scale import PhysicalQubitScalable2D


@dataclass
class PlaquetteLayer(BaseLayer):
    """Represents a layer with a template and some plaquettes.

    This class implements the layer interface by using a template and some
    plaquettes. This is the preferred way of representing a layer.
    """

    template: RectangularTemplate
    plaquettes: Plaquettes

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.template.scalable_shape * self.template._default_shift

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
