"""Defines templates representing logical qubits and its constituent parts."""

from collections.abc import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.templates.base import BorderIndices, RectangularTemplate
from tqec.templates.enums import TemplateBorder
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import LinearFunction, PlaquetteScalable2D


class QubitTemplate(RectangularTemplate):
    """An error-corrected qubit.

    The below text represents this template for an input ``k == 2`` ::

        1  5  6  5  6  2
        7  9 10  9 10 11
        8 10  9 10  9 12
        7  9 10  9 10 11
        8 10  9 10  9 12
        3 13 14 13 14  4

    """

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))

        ret = numpy.zeros(self.shape(k).to_numpy_shape(), dtype=numpy.int_)

        # The four corners
        ret[0, 0] = plaquette_indices[0]
        ret[0, -1] = plaquette_indices[1]
        ret[-1, 0] = plaquette_indices[2]
        ret[-1, -1] = plaquette_indices[3]
        # The up side
        ret[0, 1:-1:2] = plaquette_indices[4]
        ret[0, 2:-1:2] = plaquette_indices[5]
        # The left side
        ret[1:-1:2, 0] = plaquette_indices[6]
        ret[2:-1:2, 0] = plaquette_indices[7]
        # The center
        ret[1:-1:2, 1:-1:2] = plaquette_indices[8]
        ret[2:-1:2, 2:-1:2] = plaquette_indices[8]
        ret[1:-1:2, 2:-1:2] = plaquette_indices[9]
        ret[2:-1:2, 1:-1:2] = plaquette_indices[9]
        # The right side
        ret[1:-1:2, -1] = plaquette_indices[10]
        ret[2:-1:2, -1] = plaquette_indices[11]
        # The bottom side
        ret[-1, 1:-1:2] = plaquette_indices[12]
        ret[-1, 2:-1:2] = plaquette_indices[13]

        return ret

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        return PlaquetteScalable2D(LinearFunction(2, 2), LinearFunction(2, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 14

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP:
                return BorderIndices(1, 5, 6, 2)
            case TemplateBorder.BOTTOM:
                return BorderIndices(3, 13, 14, 4)
            case TemplateBorder.LEFT:
                return BorderIndices(1, 7, 8, 3)
            case TemplateBorder.RIGHT:
                return BorderIndices(2, 11, 12, 4)


class QubitSpatialCubeTemplate(RectangularTemplate):
    """An error-corrected qubit that has all the spatial boundaries in the same basis.

    The below text represents this template for an input ``k == 4`` ::

         1   9  10   9  10   9  10   9  10   2
        11   5  17  13  17  13  17  13   6  21
        12  20  13  17  13  17  13  17  14  22
        11  16  20  13  17  13  17  14  18  21
        12  20  16  20  13  17  14  18  14  22
        11  16  20  16  19  15  18  14  18  21
        12  20  16  19  15  19  15  18  14  22
        11  16  19  15  19  15  19  15  18  21
        12   7  15  19  15  19  15  19   8  22
         3  23  24  23  24  23  24  23  24   4

    Warning:
        For ``k == 1``, this template does not include any of the plaquette
        that have an index in ``[13, 17]`` and so its instantiation has a "hole"
        in the plaquette indices.

    """

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))

        shape = self.shape(k)
        ret = numpy.zeros(shape.to_numpy_shape(), dtype=numpy.int_)
        size = shape.x

        # The four corners
        ret[0, 0] = plaquette_indices[0]
        ret[0, -1] = plaquette_indices[1]
        ret[-1, 0] = plaquette_indices[2]
        ret[-1, -1] = plaquette_indices[3]
        # The up side
        ret[0, 1:-1:2] = plaquette_indices[8]
        ret[0, 2:-1:2] = plaquette_indices[9]
        # The left side
        ret[1:-1:2, 0] = plaquette_indices[10]
        ret[2:-1:2, 0] = plaquette_indices[11]
        # The center, which is the complex part.
        # Plaquette indices between 12 and 15 (both inclusive) are for plaquettes
        # on positions where (i + j) is even. Plaquettes indices between 16 and
        # 19 (both inclusive) are for plaquettes on positions where (i + j) is
        # odd. This is represented by an offset when (i + j) is odd.
        for i in range(1, size - 1):
            for j in range(1, size - 1):
                offset = 4 if (i + j) % 2 == 1 else 0
                # If the cell represented by (i, j) is:
                # - on the top (above the main diagonal and above the anti-diagonal)
                if i <= j and i <= (size - 1 - j):
                    ret[i, j] = plaquette_indices[12 + offset]
                # - on the right (above the main diagonal and below the anti-diagonal)
                elif i < j and i > (size - 1 - j):
                    ret[i, j] = plaquette_indices[13 + offset]
                # - on the bottom (below the main diagonal and below the anti-diagonal)
                elif i >= j and i >= (size - 1 - j):
                    ret[i, j] = plaquette_indices[14 + offset]
                # - on the left (below the main diagonal and above the anti-diagonal)
                elif i > j and i < (size - 1 - j):
                    ret[i, j] = plaquette_indices[15 + offset]

        ret[1, 1] = plaquette_indices[4]
        ret[1, -2] = plaquette_indices[5]
        ret[-2, 1] = plaquette_indices[6]
        ret[-2, -2] = plaquette_indices[7]
        # The right side
        ret[1:-1:2, -1] = plaquette_indices[20]
        ret[2:-1:2, -1] = plaquette_indices[21]
        # The bottom side
        ret[-1, 1:-1:2] = plaquette_indices[22]
        ret[-1, 2:-1:2] = plaquette_indices[23]

        return ret

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        return PlaquetteScalable2D(LinearFunction(2, 2), LinearFunction(2, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 24

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP:
                return BorderIndices(1, 9, 10, 2)
            case TemplateBorder.BOTTOM:
                return BorderIndices(3, 23, 24, 4)
            case TemplateBorder.LEFT:
                return BorderIndices(1, 11, 12, 3)
            case TemplateBorder.RIGHT:
                return BorderIndices(2, 21, 22, 4)


class QubitVerticalBorders(RectangularTemplate):
    """Two vertical sides of neighbouring error-corrected qubits glued together.

    The below text represents this template for an input ``k == 2`` ::
        1 2
        5 7
        6 8
        5 7
        6 8
        3 4

    """

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))
        ret = numpy.zeros(self.shape(k).to_numpy_shape(), dtype=numpy.int_)
        # The four corners
        ret[0, 0] = plaquette_indices[0]
        ret[0, -1] = plaquette_indices[1]
        ret[-1, 0] = plaquette_indices[2]
        ret[-1, -1] = plaquette_indices[3]
        # The left side
        ret[1:-1:2, 0] = plaquette_indices[4]
        ret[2:-1:2, 0] = plaquette_indices[5]
        # The right side
        ret[1:-1:2, -1] = plaquette_indices[6]
        ret[2:-1:2, -1] = plaquette_indices[7]
        return ret

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        """Return a scalable version of the template shape."""
        return PlaquetteScalable2D(LinearFunction(0, 2), LinearFunction(2, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 8

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP | TemplateBorder.BOTTOM:
                raise TQECError(
                    f"Template {self.__class__.__name__} does not have "
                    f"repeating elements on the {border.name} border."
                )
            case TemplateBorder.LEFT:
                return BorderIndices(1, 5, 6, 3)
            case TemplateBorder.RIGHT:
                return BorderIndices(2, 7, 8, 4)


class QubitHorizontalBorders(RectangularTemplate):
    """Two horizontal sides of neighbouring error-corrected qubits glued together.

    The below text represents this template for an input ``k == 2`` ::
        1 5 6 5 6 2
        3 7 8 7 8 4

    """

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))
        ret = numpy.zeros(self.shape(k).to_numpy_shape(), dtype=numpy.int_)
        # The four corners
        ret[0, 0] = plaquette_indices[0]
        ret[0, -1] = plaquette_indices[1]
        ret[-1, 0] = plaquette_indices[2]
        ret[-1, -1] = plaquette_indices[3]
        # The up side
        ret[0, 1:-1:2] = plaquette_indices[4]
        ret[0, 2:-1:2] = plaquette_indices[5]
        # The bottom side
        ret[-1, 1:-1:2] = plaquette_indices[6]
        ret[-1, 2:-1:2] = plaquette_indices[7]
        return ret

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        return PlaquetteScalable2D(LinearFunction(2, 2), LinearFunction(0, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 8

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP:
                return BorderIndices(1, 5, 6, 2)
            case TemplateBorder.BOTTOM:
                return BorderIndices(3, 7, 8, 4)
            case TemplateBorder.LEFT | TemplateBorder.RIGHT:
                raise TQECError(
                    f"Template {self.__class__.__name__} does not have repeating "
                    f"elements on the {border.name} border."
                )
