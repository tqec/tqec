"""Defines the base classes for templates: :class:`Template` and
:class:`RectangularTemplate`."""

from abc import ABC, abstractmethod
from typing import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.enums import Orientation
from tqec.exceptions import TQECException
from tqec.position import Displacement, Position2D, Shape2D
from tqec.scale import Scalable2D, round_or_fail
from tqec.templates.indices.subtemplates import (
    UniqueSubTemplates,
    get_spatially_distinct_subtemplates,
)


class Template(ABC):
    """Base class for all the templates.

    This class is the base of all templates and provide the necessary
    interface that all templates should implement to be usable by the
    library.
    """

    def __init__(self, default_increments: Displacement | None = None) -> None:
        """Construct an instance of the template.

        Args:
            default_increments: default increments between two plaquettes. Defaults
                to ``Displacement(2, 2)`` when ``None``
        """
        super().__init__()
        self._default_increments = default_increments or Displacement(2, 2)

    @abstractmethod
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        """Generate the numpy array representing the template.

        Args:
            k: scaling parameter used to instantiate the template.
            plaquette_indices: the plaquette indices that will be forwarded to
                the underlying Shape instance's instantiate method. Defaults
                to ``range(1, self.expected_plaquettes_number + 1)`` if ``None``.

        Returns:
            a numpy array with the given plaquette indices arranged according to
            the underlying shape of the template.
        """

    def shape(self, k: int) -> Shape2D:
        """Returns the current template shape."""
        sshape = self.scalable_shape
        return Shape2D(round_or_fail(sshape.x(k)), round_or_fail(sshape.y(k)))

    @property
    @abstractmethod
    def scalable_shape(self) -> Scalable2D:
        """Returns a scalable version of the template shape."""

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
        shape = self.shape(k)
        midline_shape, iteration_shape = shape.x, shape.y
        if midline_shape % 2 == 1:
            raise TQECException(
                "Midline is not defined for odd "
                + f"{'height' if orientation == Orientation.HORIZONTAL else 'width'}."
            )
        midline = midline_shape // 2 - 1
        if orientation == Orientation.VERTICAL:
            return [(row, midline) for row in range(iteration_shape)]
        return [(midline, column) for column in range(iteration_shape)]

    @property
    @abstractmethod
    def expected_plaquettes_number(self) -> int:
        """Returns the number of plaquettes expected from the
        :py:meth:`instantiate` method.

        Returns:
            the number of plaquettes expected from the :py:meth:`instantiate` method.
        """

    def get_increments(self) -> Displacement:
        """Get the default increments of the template.

        Returns:
            a displacement of the default increments in the x and y directions.
        """
        return self._default_increments

    def get_spatially_distinct_subtemplates(
        self, k: int, manhattan_radius: int = 1, avoid_zero_plaquettes: bool = True
    ) -> UniqueSubTemplates:
        """Returns a representation of all the distinct sub-templates of the
        provided manhattan radius.

        Note:
            This method will likely be inefficient for large templates (i.e., large
            values of `k`) or for large Manhattan radiuses, both in terms of memory
            used and computation time.
            Subclasses are invited to reimplement that method using a specialized
            algorithm (or hard-coded values) to speed things up.

        Args:
            k: scaling parameter used to instantiate the template.
            manhattan_radius: radius of the considered ball using the Manhattan
                distance. Only squares with sides of ``2*manhattan_radius+1``
                plaquettes will be considered.
            avoid_zero_plaquettes: ``True`` if sub-templates with an empty plaquette
                (i.e., 0 value in the instantiation of the
                :class:`~tqec.templates.indices.base.Template` instance) at its center
                should be ignored. Default to ``True``.

        Returns:
            a representation of all the sub-templates found.
        """
        return get_spatially_distinct_subtemplates(
            self.instantiate(k), manhattan_radius, avoid_zero_plaquettes
        )

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
        return Position2D(0, 0)


class RectangularTemplate(Template):
    """Base class for all the templates that have a rectangular shape."""

    @override
    def get_midline_plaquettes(
        self, k: int, orientation: Orientation = Orientation.HORIZONTAL
    ) -> list[tuple[int, int]]:
        shape = self.shape(k)
        midline_shape, iteration_shape = shape.x, shape.y
        if midline_shape % 2 == 1:
            raise TQECException(
                "Midline is not defined for odd "
                + f"{'height' if orientation == Orientation.HORIZONTAL else 'width'}."
            )
        midline = midline_shape // 2 - 1
        if orientation == Orientation.VERTICAL:
            return [(row, midline) for row in range(iteration_shape)]
        return [(midline, column) for column in range(iteration_shape)]
