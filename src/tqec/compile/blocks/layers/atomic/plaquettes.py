from __future__ import annotations

from typing import Final, Iterable

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.spatial import EXPECTED_SPATIAL_BORDER_WIDTH
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Shift2D
from tqec.utils.scale import (
    LinearFunction,
    PhysicalQubitScalable2D,
    PlaquetteScalable2D,
)


class PlaquetteLayer(BaseLayer):
    def __init__(
        self,
        template: RectangularTemplate,
        plaquettes: Plaquettes,
        spatial_borders_removed: frozenset[SpatialBlockBorder] = frozenset(),
    ) -> None:
        """Represents a layer with a template and some plaquettes.

        This class implements the layer interface by using a template and some
        plaquettes. This is the preferred way of representing a layer.

        Raises:
            TQECException: if the provided ``template`` increments do not match
                with the expected spatial border width.
            TQECException: if the provided ``template`` and
                ``spatial_borders_removed`` can lead to empty instantiations for
                ``k >= 1``.
        """
        super().__init__()
        # Shortening variable name for convenience
        EW: Final[int] = EXPECTED_SPATIAL_BORDER_WIDTH
        expected_shifts = Shift2D(EW, EW)
        if (shifts := template.get_increments()) != expected_shifts:
            raise TQECException(
                f"Spatial borders are expected to be {EW} qubits large. Got a "
                f"Template instance with {shifts:=}. Removing a border from "
                f"such a template instance would remove more than {EW} qubits, "
                "which is not supported."
            )
        # We require the template shape to be strictly positive for any value of
        # k > 0.
        shape = PlaquetteLayer._get_template_shape(template, spatial_borders_removed)
        shape1 = shape.to_numpy_shape(1)
        # Check that the shape is valid (i.e., strictly positive) for k == 1.
        if not all(coord > 0 for coord in shape1):
            raise TQECException(
                "The provided template/spatial_borders_removed combo leads to an "
                f"invalid template shape ({shape1}) for k == 1. "
                f"{PlaquetteLayer.__name__} instances do not support empty templates."
            )
        # Check that the shape is either increasing or is constant for both
        # coordinates.
        if shape.x.slope < 0 or shape.y.slope < 0:
            raise TQECException(
                "The provided template does have a strictly decreasing shape, "
                "which will eventually lead to an empty instantiation, which is "
                f"not supported by {PlaquetteLayer.__name__} instances."
            )

        self._template = template
        self._plaquettes = plaquettes
        self._spatial_borders_removed = spatial_borders_removed

    @staticmethod
    def _get_template_shape(
        template: RectangularTemplate,
        spatial_borders_removed: frozenset[SpatialBlockBorder],
    ) -> PlaquetteScalable2D:
        """Get the shape of the provided ``template``, taking into account the
        removed spatial borders.

        Args:
            template: template to get the shape from.
            spatial_borders_removed: a collection of all the spatial borders
                that have been removed.

        Returns:
            the shape of the provided template with the provided borders removed.
        """
        base_shape = template.scalable_shape
        return PlaquetteScalable2D(
            base_shape.x
            - (SpatialBlockBorder.X_NEGATIVE in spatial_borders_removed)
            - (SpatialBlockBorder.X_POSITIVE in spatial_borders_removed),
            base_shape.y
            - (SpatialBlockBorder.Y_NEGATIVE in spatial_borders_removed)
            - (SpatialBlockBorder.Y_POSITIVE in spatial_borders_removed),
        )

    @property
    def template(self) -> RectangularTemplate:
        return self._template

    @property
    def plaquettes(self) -> Plaquettes:
        return self._plaquettes

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        tshape = PlaquetteLayer._get_template_shape(
            self.template, self._spatial_borders_removed
        )
        initial_qubit_offset = PhysicalQubitScalable2D(
            LinearFunction(0, 1), LinearFunction(0, 1)
        )
        return tshape * self.template.get_increments() + initial_qubit_offset

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> PlaquetteLayer:
        # Warning: depends on the fact that plaquette indices on the border of
        # a template are ONLY on this border.
        borders = frozenset(borders)
        border_indices: set[int] = set()
        for border in borders:
            border_indices.update(
                self.template.get_border_indices(border.to_template_border())
            )
        return PlaquetteLayer(
            self.template,
            self.plaquettes.without_plaquettes(border_indices),
            spatial_borders_removed=borders,
        )
