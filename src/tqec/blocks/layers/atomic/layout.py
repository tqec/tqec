from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.layout import LayoutTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import PhysicalQubitScalable2D


@dataclass
class LayoutLayer(BaseLayer):
    """Represents a layer with a spatial footprint that is defined by a
    :class:`~tqec.templates.layout.LayoutTemplate` instance.
    """

    template: LayoutTemplate
    plaquettes: Plaquettes

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.template.scalable_shape * self.template._default_shift

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> LayoutLayer:
        clsname = self.__class__.__name__
        raise TQECException(f"Cannot trim spatial borders of a {clsname} instance.")
