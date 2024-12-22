from dataclasses import dataclass

from tqec.enums import Orientation
from tqec.plaquette.frozendefaultdict import FrozenDefaultDict
from tqec.plaquette.rpng import RPNGDescription
from tqec.position import Displacement, Position2D, Shape2D
from tqec.scale import Scalable2D
from tqec.templates.indices.base import Template


@dataclass
class RPNGTemplate:
    template: Template
    mapping: FrozenDefaultDict[int, RPNGDescription]

    def instantiate(self, k: int) -> list[list[RPNGDescription]]:
        indices = self.template.instantiate(k)
        return [[self.mapping[i] for i in row] for row in indices]

    def shape(self, k: int) -> Shape2D:
        """Returns the current template shape."""
        return self.template.shape(k)

    @property
    def scalable_shape(self) -> Scalable2D:
        """Returns a scalable version of the template shape."""
        return self.template.scalable_shape

    def get_midline_plaquettes(
        self, k: int, orientation: Orientation = Orientation.HORIZONTAL
    ) -> list[tuple[int, int]]:
        """Returns the default observable qubits for the template.

        If the template has a simple shape, this returns the plaquettes on the
        "midline" of the template.
        By convention, it returns the plaquettes above the midline for the
        horizontal case and to the left of the midline for the vertical case.

        Args:
            orientation: Horizontal or vertical qubits. Defaults to horizontal.

        Returns:
            The sequence of qubits and offsets.

        Raises:
            TQECException: If the midline is not uniquely defined.
        """
        return self.template.get_midline_plaquettes(k, orientation)

    def get_increments(self) -> Displacement:
        """Get the default increments of the template.

        Returns:
            a displacement of the default increments in the x and y directions.
        """
        return self.template.get_increments()

    def instantiation_origin(self, k: int) -> Position2D:
        """Coordinates of the top-left entry origin.

        This property returns the coordinates of the origin of the plaquette
        (:class:`~tqec.plaquette.plaquette.Plaquette.origin`) that corresponds
        to the top-left entry of the array returned by
        :meth:`~tqec.templates.indices.base.Template.instantiate`.

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
            :meth:`~tqec.templates.indices.base.Template.instantiate`.
        """
        return self.template.instantiation_origin(k)
