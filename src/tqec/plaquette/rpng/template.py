from dataclasses import dataclass
from typing import Generic, TypeVar

from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.base import Template
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import PlaquettePosition2D, PlaquetteShape2D, Shift2D
from tqec.utils.scale import PlaquetteScalable2D

T = TypeVar("T", bound=Template, covariant=True)


@dataclass
class RPNGTemplate(Generic[T]):
    template: T
    mapping: FrozenDefaultDict[int, RPNGDescription]

    def instantiate(self, k: int) -> list[list[RPNGDescription]]:
        indices = self.template.instantiate(k)
        return [[self.mapping[i] for i in row] for row in indices]

    def shape(self, k: int) -> PlaquetteShape2D:
        """Returns the current template shape."""
        return self.template.shape(k)

    @property
    def scalable_shape(self) -> PlaquetteScalable2D:
        """Returns a scalable version of the template shape."""
        return self.template.scalable_shape

    def get_increments(self) -> Shift2D:
        """Get the default increments of the template.

        Returns:
            a displacement of the default increments in the x and y directions.

        """
        return self.template.get_increments()

    def instantiation_origin(self, k: int) -> PlaquettePosition2D:
        """Coordinates of the top-left entry origin.

        This property returns the coordinates of the origin of the plaquette
        (:class:`~tqec.plaquette.plaquette.Plaquette.origin`) that corresponds
        to the top-left entry of the array returned by
        :meth:`~tqec.templates.base.Template.instantiate`.

        Note:
            the returned coordinates are in plaquette coordinates. That means
            that, if you want to get the coordinates of the top-left plaquette
            origin (which is a qubit), you should multiply the coordinates
            returned by this method by the tiling increments.

        Args:
            k: scaling parameter used to instantiate the template.

        Returns:
            the coordinates of the origin of the plaquette
            (:class:`~tqec.plaquette.plaquette.Plaquette.origin`) that corresponds
            to the top-left entry of the array returned by
            :meth:`~tqec.templates.base.Template.instantiate`.

        """
        return self.template.instantiation_origin(k)
