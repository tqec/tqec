from collections.abc import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.templates.base import BorderIndices, RectangularTemplate
from tqec.templates.enums import TemplateBorder
from tqec.utils.position import Shift2D
from tqec.utils.scale import LinearFunction, PlaquetteScalable2D


class FixedTemplate(RectangularTemplate):
    """A fixed template, only used internally for testing."""

    def __init__(
        self,
        indices: Sequence[Sequence[int]],
        default_increments: Shift2D | None = None,
    ) -> None:
        super().__init__(default_increments)
        self._indices: npt.NDArray[numpy.int_] = numpy.array([list(line) for line in indices])

    @override
    def instantiate(
        self, k: int = 0, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))

        return numpy.array(plaquette_indices)[self._indices]

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        y, x = self._indices.shape
        return PlaquetteScalable2D(LinearFunction(0, x), LinearFunction(0, y))

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        return max((max(line, default=0) for line in self._indices), default=0) + 1

    @override
    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        raise NotImplementedError()
