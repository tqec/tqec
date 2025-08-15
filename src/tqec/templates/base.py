"""Defines the base classes for templates: :class:`Template` and :class:`RectangularTemplate`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy
import numpy.typing as npt

from tqec.templates.enums import TemplateBorder
from tqec.templates.subtemplates import (
    UniqueSubTemplates,
    get_spatially_distinct_subtemplates,
)
from tqec.utils.position import (
    BlockPosition2D,
    PlaquettePosition2D,
    PlaquetteShape2D,
    Shift2D,
)
from tqec.utils.scale import PlaquetteScalable2D, round_or_fail


class Template(ABC):
    """Base class for all the templates.

    This class is the base of all templates and provide the necessary interface that all templates
    should implement to be usable by the library.

    """

    def __init__(self, default_increments: Shift2D | None = None) -> None:
        """Construct an instance of the template.

        Args:
            default_increments: default increments between two plaquettes. Defaults
                to ``Displacement(2, 2)`` when ``None``

        """
        super().__init__()
        self._default_shift = default_increments or Shift2D(2, 2)

    def __hash__(self) -> int:
        return hash((type(self), self._default_shift))

    def __eq__(self, value: Any) -> bool:
        return type(self) is type(value) and self._default_shift == value._default_shift

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

    def instantiate_list(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> list[list[int]]:
        """Generate a 2-dimensional list of integers representing the template.

        This method is equivalent to
        ``self.instantiate(k, plaquette_indices).tolist()`` but has a stricter
        and more correct typing than calling ``tolist`` on a numpy array.

        Args:
            k: scaling parameter used to instantiate the template.
            plaquette_indices: the plaquette indices that will be forwarded to
                the underlying Shape instance's instantiate method. Defaults
                to ``range(1, self.expected_plaquettes_number + 1)`` if ``None``.

        Returns:
            a 2-dimensional list (i.e., a list of lists) with the given
            plaquette indices arranged according to the underlying shape of the
            template.

        """
        instantiation = self.instantiate(k, plaquette_indices=plaquette_indices)
        m, n = instantiation.shape
        ret: list[list[int]] = []
        for i in range(m):
            ret.append([])
            for j in range(n):
                ret[-1].append(int(instantiation[i, j]))
        return ret

    def shape(self, k: int) -> PlaquetteShape2D:
        """Return the current template shape."""
        sshape = self.scalable_shape
        return PlaquetteShape2D(round_or_fail(sshape.x(k)), round_or_fail(sshape.y(k)))

    @property
    @abstractmethod
    def scalable_shape(self) -> PlaquetteScalable2D:
        """Return a scalable version of the template shape."""

    @property
    @abstractmethod
    def expected_plaquettes_number(self) -> int:
        """Return the number of plaquettes expected from the :py:meth:`instantiate` method.

        Returns:
            the number of plaquettes expected from the :py:meth:`instantiate` method.

        """

    def get_increments(self) -> Shift2D:
        """Get the default increments of the template.

        Returns:
            a displacement of the default increments in the x and y directions.

        """
        return self._default_shift

    def get_spatially_distinct_subtemplates(
        self, k: int, manhattan_radius: int = 1, avoid_zero_plaquettes: bool = True
    ) -> UniqueSubTemplates:
        """Return a representation of the distinct sub-templates of the provided Manhattan radius.

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
                :class:`~tqec.templates.base.Template` instance) at its center
                should be ignored. Default to ``True``.

        Returns:
            a representation of all the sub-templates found.

        """
        return get_spatially_distinct_subtemplates(  # pragma: no cover
            self.instantiate(k), manhattan_radius, avoid_zero_plaquettes
        )

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
        return BlockPosition2D(0, 0).get_top_left_plaquette_position(self.shape(k))


@dataclass(frozen=True)
class BorderIndices:
    """Stores indices on the border of a rectangular template.

    Attributes:
        top_left_corner: non-repeating index at the top or left part of the
            border.
        first_repeating: first repeating index on the border "bulk".
        second_repeating: second repeating index on the border "bulk".
        bottom_right_corner: non-repeating index at the bottom or right part of
            the border.

    """

    top_left_corner: int
    first_repeating: int
    second_repeating: int
    bottom_right_corner: int

    def to(self, other: BorderIndices) -> dict[int, int]:
        """Return a mapping from ``self`` to ``other``.

        This method returns a mapping from the indices stored in ``self`` to the
        indices stored in ``other``.

        Args:
            other: indices from another border.

        Returns:
            a mapping from the indices stored in ``self`` to the indices stored
            in ``other``.

        """
        return {s: o for s, o in zip(self, other)}

    def __iter__(self) -> Iterator[int]:
        yield from (
            self.top_left_corner,
            self.first_repeating,
            self.second_repeating,
            self.bottom_right_corner,
        )


class RectangularTemplate(Template):
    """Base class for all the templates that have a rectangular shape."""

    @abstractmethod
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        """Return the indices on the provided ``border``.

        Args:
            border: side of the template instance for which the indices are
                needed.

        Returns:
            a description of the indices present on the provided ``border`` of
            the represented template.

        """
        pass
