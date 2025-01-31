"""Defines templates representing logical qubits and its constituent parts."""

import warnings
from typing import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.templates.base import BorderIndices, RectangularTemplate
from tqec.templates.enums import TemplateBorder
from tqec.utils.exceptions import TQECException, TQECWarning
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
        11   5  17  13  17  13  17  13   6  18
        12  17  13  17  13  17  13  17  14  19
        11  16  17  13  17  13  17  14  17  18
        12  17  16  17  13  17  14  17  14  19
        11  16  17  16  17  15  17  14  17  18
        12  17  16  17  15  17  15  17  14  19
        11  16  17  15  17  15  17  15  17  18
        12   7  15  17  15  17  15  17   8  19
         3  20  21  20  21  20  21  20  21   4

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

        if k == 1:
            warnings.warn(
                "Instantiating QubitSpatialCubeTemplate with k=1. The "
                "instantiation array returned will not have any plaquette with "
                "an index in [13, 17], which might break other parts of the "
                "library.",
                TQECWarning,
            )

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
        # Start by plaquette_indices[16] which is the plaquette that is
        # uniformly spread on the template
        ret[1:-1:2, 2:-1:2] = plaquette_indices[16]
        ret[2:-1:2, 1:-1:2] = plaquette_indices[16]
        # Now initialize the other plaquettes
        for i in range(1, size - 1):
            # We want (i + j) to be even, because that are the only places where
            # we should set plaquettes. We do that directly in the range expression.
            # We need to avoid 0 here because it is the border of the template.
            for j in range(1 if i % 2 == 1 else 2, size - 1, 2):
                # If the cell represented by (i, j) is:
                # - on the top (above the main diagonal and above the anti-diagonal)
                if i <= j and i < (size - 1 - j):
                    ret[i, j] = plaquette_indices[12]
                # - on the right (above the main diagonal and below the anti-diagonal)
                elif i < j and i > (size - 1 - j):
                    ret[i, j] = plaquette_indices[13]
                # - on the bottom (below the main diagonal and below the anti-diagonal)
                elif i >= j and i > (size - 1 - j):
                    ret[i, j] = plaquette_indices[14]
                # - on the left (below the main diagonal and above the anti-diagonal)
                elif i > j and i < (size - 1 - j):
                    ret[i, j] = plaquette_indices[15]

        ret[1, 1] = plaquette_indices[4]
        ret[1, -2] = plaquette_indices[5]
        ret[-2, 1] = plaquette_indices[6]
        ret[-2, -2] = plaquette_indices[7]
        # The right side
        ret[1:-1:2, -1] = plaquette_indices[17]
        ret[2:-1:2, -1] = plaquette_indices[18]
        # The bottom side
        ret[-1, 1:-1:2] = plaquette_indices[19]
        ret[-1, 2:-1:2] = plaquette_indices[20]

        return ret

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        return PlaquetteScalable2D(LinearFunction(2, 2), LinearFunction(2, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 21

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP:
                return BorderIndices(1, 9, 10, 2)
            case TemplateBorder.BOTTOM:
                return BorderIndices(3, 20, 21, 4)
            case TemplateBorder.LEFT:
                return BorderIndices(1, 11, 12, 3)
            case TemplateBorder.RIGHT:
                return BorderIndices(2, 18, 19, 4)


class QubitVerticalBorders(RectangularTemplate):
    """Two vertical sides of neighbouring error-corrected qubits glued
    together.

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
        """Returns a scalable version of the template shape."""
        return PlaquetteScalable2D(LinearFunction(0, 2), LinearFunction(2, 2))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return 8

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        match border:
            case TemplateBorder.TOP | TemplateBorder.BOTTOM:
                raise TQECException(
                    f"Template {self.__class__.__name__} does not have repeating "
                    f"elements on the {border.name} border."
                )
            case TemplateBorder.LEFT:
                return BorderIndices(1, 5, 6, 3)
            case TemplateBorder.RIGHT:
                return BorderIndices(2, 7, 8, 4)


class QubitHorizontalBorders(RectangularTemplate):
    """Two horizontal sides of neighbouring error-corrected qubits glued
    together.

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
                raise TQECException(
                    f"Template {self.__class__.__name__} does not have repeating "
                    f"elements on the {border.name} border."
                )
