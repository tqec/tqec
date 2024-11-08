"""Defines a high-level template composing several sub-templates:
:class:`LayoutTemplate`.

This module defines a :class:`~tqec.templates.base.Template` child class that
is able to represent several :class:`~tqec.templates.base.RectangularTemplate`
instances with the same scalable shape. Each of the managed
:class:`~tqec.templates.base.RectangularTemplate` instance is linked to a unique
2-dimensional position on an infinite 2-dimensional grid.

Example
-------

A grid of :math:`2 \\times 2` logical qubits can be represented with

.. code-block:: python

    from tqec.position import Position2D
    from tqec.templates.layout import LayoutTemplate
    from tqec.templates.qubit import QubitTemplate

    qubit = QubitTemplate()
    grid = LayoutTemplate(
        {
            Position2D(0, 0): qubit,
            Position2D(0, 1): qubit,
            Position2D(1, 0): qubit,
            Position2D(1, 1): qubit,
        }
    )

Being a :class:`~tqec.templates.base.Template` instance, the above constructed
``grid`` can be displayed with

.. code-block:: python

    from tqec.templates.display import display_template

    display_template(qubit, 2)
    print("=" * 50)
    display_template(grid, 2)

which outputs

.. code-block:: text

    1   5   6   5   6   2
    7   9  10   9  10  11
    8  10   9  10   9  12
    7   9  10   9  10  11
    8  10   9  10   9  12
    3  13  14  13  14   4
    ==================================================
     1   5   6   5   6   2  29  33  34  33  34  30
     7   9  10   9  10  11  35  37  38  37  38  39
     8  10   9  10   9  12  36  38  37  38  37  40
     7   9  10   9  10  11  35  37  38  37  38  39
     8  10   9  10   9  12  36  38  37  38  37  40
     3  13  14  13  14   4  31  41  42  41  42  32
    15  19  20  19  20  16  43  47  48  47  48  44
    21  23  24  23  24  25  49  51  52  51  52  53
    22  24  23  24  23  26  50  52  51  52  51  54
    21  23  24  23  24  25  49  51  52  51  52  53
    22  24  23  24  23  26  50  52  51  52  51  54
    17  27  28  27  28  18  45  55  56  55  56  46
"""

from copy import deepcopy
from typing import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.exceptions import TQECException
from tqec.position import Displacement, Position2D, Shape2D
from tqec.scale import Scalable2D
from tqec.templates.base import RectangularTemplate


class LayoutTemplate(RectangularTemplate):
    def __init__(
        self,
        element_layout: dict[Position2D, RectangularTemplate],
        default_increments: Displacement | None = None,
    ) -> None:
        """A template representing a layout of other templates.

        Each element template in the layout is placed at a specific position in
        the 2D grid.

        Note:
            The provided template positions have only one restriction: two
            templates should not be at the same position.
            In particular, this class does not require that the provided
            template are spatially connected or entirely cover a rectangular
            portion of the 2 spatial dimensions.

        Args:
            element_layout: a dictionary with the position of the element
                templates in the layout as keys and the templates as values.
            default_increments: default increments between two plaquettes. Defaults
                to ``Displacement(2, 2)`` when ``None``.
        """
        super().__init__(default_increments)
        if not element_layout:
            raise TQECException("Cannot create a layout with an empty template map.")

        scalable_shapes = {
            template.scalable_shape for template in element_layout.values()
        }
        if len(scalable_shapes) != 1:
            raise TQECException(
                "All templates in the layout should have the same scalable shape."
            )
        self._element_scalable_shape = scalable_shapes.pop()

        all_positions = list(element_layout.keys())
        min_x = min(position.x for position in all_positions)
        max_x = max(position.x for position in all_positions)
        min_y = min(position.y for position in all_positions)
        max_y = max(position.y for position in all_positions)
        # Shift the bounding box to the origin
        self._origin_shift = Displacement(min_x, min_y)
        self._nx = max_x - min_x + 1
        self._ny = max_y - min_y + 1

        self._layout = deepcopy(element_layout)

    def get_indices_map_for_instantiation(
        self,
        instantiate_indices: Sequence[int] | None = None,
    ) -> dict[Position2D, dict[int, int]]:
        """Get one index map for each of the templates in the layout.

        This method is used internally by :meth:`LayoutTemplate.instantiate` and
        can be used externally to get a map from the instantiation indices used by
        each of the individual :class:`~tqec.templates.base.Template` instances
        stored in ``self`` to the global instantiation index used.

        Args:
            instantiate_indices: global indices used to instantiate ``self``.
                Have the same meaning and defaults as the ``plaquette_indices``
                parameter in :meth:`LayoutTemplate.instantiate`.
                Defaults to None.

        Returns:
            a map from positions to instantiation index maps. Each instantiation
            index map is a bijection from the template instantiation indices (going
            from ``1`` to ``template.expected_plaquettes_number``) to the global
            indices that are used in :meth:`LayoutTemplate.instantiate` (going
            from ``N`` to ``N + template.expected_plaquettes_number - 1`` where
            ``N`` depends on the other :class:`~tqec.templates.base.Template`
            instances managed by ``self``).
        """
        if instantiate_indices is None:
            instantiate_indices = list(range(1, self.expected_plaquettes_number + 1))
        index_count = 0
        indices_map = {}
        for position, template in self._layout.items():
            indices_map[position] = {
                i + 1: instantiate_indices[i + index_count]
                for i in range(template.expected_plaquettes_number)
            }
            index_count += template.expected_plaquettes_number
        return indices_map

    @property
    def origin_shift(self) -> Displacement:
        """Returns the shift that should be applied to the global origin to
        become the template origin.

        Due to how :class:`LayoutTemplate` organizes the
        :class:`~tqec.templates.base.Template` instances it manages, it is entirely
        possible (and valid) for the template to not be aligned with the global
        origin.

        For example, the following instance exhibit this behaviour:

        .. code-block:: python

            not_on_origin = LayoutTemplate({Position2D(1, 1): QubitTemplate()})
            assert not_on_origin.origin_shift == Position2D(1, 1)

        Returns:
            the shift that should be applied to the global origin to become the
            template origin.
        """
        return self._origin_shift

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        """Returns a scalable version of the template shape."""
        return Scalable2D(
            self._nx * self._element_scalable_shape.x,
            self._ny * self._element_scalable_shape.y,
        )

    def element_shape(self, k: int) -> Shape2D:
        """Return the uniform shape of the element templates."""
        return self._element_scalable_shape.to_shape_2d(k)

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        """Returns the number of plaquettes expected from the `instantiate`
        method.

        Returns:
            the number of plaquettes expected from the `instantiate` method.
        """
        return sum(
            template.expected_plaquettes_number for template in self._layout.values()
        )

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        """Generate the numpy array representing the template.

        Args:
            k: scaling parameter used to instantiate the template.
            plaquette_indices: the plaquette indices that will be forwarded to
                the underlying Template instance's instantiate method. Defaults
                to `range(1, self.expected_plaquettes_number + 1)` if `None`.

        Returns:
            a numpy array with the given plaquette indices arranged according to
            the underlying shape of the template.
        """
        indices_map = self.get_indices_map_for_instantiation(plaquette_indices)

        element_shape = self._element_scalable_shape.to_numpy_shape(k)
        ret = numpy.zeros(self.shape(k).to_numpy_shape(), dtype=numpy.int_)
        for pos, element in self._layout.items():
            imap = indices_map[pos]
            indices = [
                imap[i] for i in range(1, element.expected_plaquettes_number + 1)
            ]
            element_instantiation = element.instantiate(k, indices)
            shifted_pos = Position2D(
                pos.x - self.origin_shift.x, pos.y - self.origin_shift.y
            )
            ret[
                shifted_pos.y * element_shape[0] : (shifted_pos.y + 1)
                * element_shape[0],
                shifted_pos.x * element_shape[1] : (shifted_pos.x + 1)
                * element_shape[1],
            ] = element_instantiation
        return ret

    @override
    def instantiation_origin(self, k: int) -> Position2D:
        origin_shift = self.origin_shift
        element_shape = self.element_shape(k)
        return Position2D(
            origin_shift.x * element_shape.x, origin_shift.y * element_shape.y
        )
