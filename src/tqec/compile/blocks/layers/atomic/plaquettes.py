from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Literal

from typing_extensions import override

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.spatial import EXPECTED_SPATIAL_BORDER_WIDTH
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import RectangularTemplate
from tqec.utils.exceptions import TQECError
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
        trimmed_spatial_borders: frozenset[SpatialBlockBorder] = frozenset(),
    ) -> None:
        """Represent a layer with a template and some plaquettes.

        This class implements the layer interface by using a template and some
        plaquettes. This is the preferred way of representing a layer.

        Args:
            template: template used in conjunction to ``plaquettes`` to
                represent the quantum circuit implementing the layer.
            plaquettes: plaquettes used in conjunction to ``template`` to
                represent the quantum circuit implementing the layer.
            trimmed_spatial_borders: all the spatial borders that have been
                removed from the layer.

        Raises:
            TQECError: if the provided ``template`` increments do not match
                with the expected spatial border width.
            TQECError: if the provided ``template`` and
                ``trimmed_spatial_borders`` can lead to empty instantiations for
                ``k >= 1``.

        """
        super().__init__(trimmed_spatial_borders)
        self._template = template
        self._plaquettes = plaquettes
        self._post_init_check()

    def _post_init_check(self) -> None:
        # Shortening variable name for convenience
        _ew: Final[int] = EXPECTED_SPATIAL_BORDER_WIDTH
        expected_shifts = Shift2D(_ew, _ew)
        if (shifts := self._template.get_increments()) != expected_shifts:
            raise TQECError(
                f"Spatial borders are expected to be {_ew} qubits large. Got a "
                f"Template instance with {shifts:=}. Removing a border from "
                f"such a template instance would remove more than {_ew} qubits, "
                "which is not supported."
            )
        # We require the template shape to be strictly positive for any value of
        # k > 0.
        shape = PlaquetteLayer._get_template_shape(self._template, self.trimmed_spatial_borders)
        shape1 = shape.to_numpy_shape(1)
        # Check that the shape is valid (i.e., strictly positive) for k == 1.
        if not all(coord > 0 for coord in shape1):
            raise TQECError(
                "The provided template/trimmed_spatial_borders combo leads to an "
                f"invalid template shape ({shape1}) for k == 1. "
                f"{PlaquetteLayer.__name__} instances do not support empty templates."
            )
        # Check that the shape is either increasing or is constant for both
        # coordinates.
        if shape.x.slope < 0 or shape.y.slope < 0:
            raise TQECError(
                "The provided template does have a strictly decreasing shape, "
                "which will eventually lead to an empty instantiation, which is "
                f"not supported by {PlaquetteLayer.__name__} instances."
            )

    @staticmethod
    def _get_number_of_plaquettes(axis: Literal["X", "Y"], increments: int) -> int:
        # Shortening variable name for convenience
        _ew: Final[int] = EXPECTED_SPATIAL_BORDER_WIDTH
        if _ew % increments != 0:
            raise TQECError(
                f"Trying to remove {_ew} qubits from the {axis} border of a template "
                f"with increments {increments} in that axis. {_ew} % {increments} "
                "!= 0, which means that we would remove a non-integer number of "
                "plaquettes, which is not supported."
            )
        return _ew // increments

    @staticmethod
    def _get_template_shape(
        template: RectangularTemplate,
        spatial_borders_removed: frozenset[SpatialBlockBorder],
    ) -> PlaquetteScalable2D:
        """Get the shape of the provided ``template``, taking into account removed spatial borders.

        Args:
            template: template to get the shape from.
            spatial_borders_removed: a collection of all the spatial borders
                that have been removed.

        Returns:
            the shape of the provided template with the provided borders removed.

        """
        base_shape = template.scalable_shape
        # We return a shape in plaquette-coordinates. In order to know exactly the
        # number of plaquettes that will be trimmed, we need to divide
        # EXPECTED_SPATIAL_BORDER_WIDTH by the increments of the template.
        incr = template.get_increments()
        xborderp = PlaquetteLayer._get_number_of_plaquettes("X", incr.x)
        yborderp = PlaquetteLayer._get_number_of_plaquettes("X", incr.x)
        return PlaquetteScalable2D(
            base_shape.x
            - (SpatialBlockBorder.X_NEGATIVE in spatial_borders_removed) * xborderp
            - (SpatialBlockBorder.X_POSITIVE in spatial_borders_removed) * xborderp,
            base_shape.y
            - (SpatialBlockBorder.Y_NEGATIVE in spatial_borders_removed) * yborderp
            - (SpatialBlockBorder.Y_POSITIVE in spatial_borders_removed) * yborderp,
        )

    @property
    def template(self) -> RectangularTemplate:
        """Get the template stored by ``self``."""
        return self._template

    @property
    def plaquettes(self) -> Plaquettes:
        """Get the plaquettes stored by ``self``."""
        return self._plaquettes

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        tshape = PlaquetteLayer._get_template_shape(self.template, self.trimmed_spatial_borders)
        initial_qubit_offset = PhysicalQubitScalable2D(LinearFunction(0, 1), LinearFunction(0, 1))
        return tshape * self.template.get_increments() + initial_qubit_offset

    @override
    def with_spatial_borders_trimmed(self, borders: Iterable[SpatialBlockBorder]) -> PlaquetteLayer:
        # Warning: depends on the fact that plaquette indices on the border of
        # a template are ONLY on this border.
        borders = frozenset(borders)
        border_indices: set[int] = set()
        for border in borders:
            border_indices.update(self.template.get_border_indices(border.to_template_border()))
        return PlaquetteLayer(
            self.template,
            self.plaquettes.without_plaquettes(border_indices),
            trimmed_spatial_borders=self.trimmed_spatial_borders | borders,
        )

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, PlaquetteLayer)
            and self._template == value._template
            and self._plaquettes == value._plaquettes
        )

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    @property
    @override
    def scalable_num_moments(self) -> LinearFunction:
        return LinearFunction(
            0,
            max(
                (plaquette.num_moments for plaquette in self.plaquettes.collection.values()),
                default=0,
            ),
        )
