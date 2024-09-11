from copy import deepcopy
from typing import Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.exceptions import TQECException
from tqec.position import Displacement
from tqec.templates.base import RectangularTemplate
from tqec.templates.enums import TemplateSide
from tqec.templates.scale import Scalable2D


class GridTemplate(RectangularTemplate):
    def __init__(
        self,
        index_grid: Sequence[Sequence[int]],
        tiled_template: RectangularTemplate,
        k: int = 2,
        default_increments: Displacement | None = None,
    ) -> None:
        super().__init__(k, default_increments)
        if len(index_grid) == 0:
            raise TQECException("Cannot create a grid with no row.")
        if len(index_grid[0]) == 0:
            raise TQECException("Cannot create a grid with no column.")
        indices_in_grid = numpy.unique(index_grid)
        if indices_in_grid[0] not in [0, 1] or not numpy.all(
            numpy.equal(
                indices_in_grid,
                numpy.arange(
                    indices_in_grid[0], indices_in_grid[0] + len(indices_in_grid)
                ),
            )
        ):
            raise TQECException(
                "We require indices in the provided grid to be a contiguous "
                "sequence of integers starting from either 0 (if some qubits "
                "are not used) or 1."
            )
        self._rows = len(index_grid)
        self._cols = len(index_grid[0])
        self._grid = index_grid
        self._sorted_indices_in_grid = indices_in_grid
        self._tiled_template = deepcopy(tiled_template)
        self._tiled_template.scale_to(k)

    def _map_plaquette_indices(
        self, row: int, col: int, plaquette_indices: Sequence[int]
    ) -> list[int]:
        offset = self._tiled_template.expected_plaquettes_number * self._grid[row][col]
        return [pi + offset for pi in plaquette_indices]

    @override
    def scale_to(self, k: int) -> None:
        self._k = k
        self._tiled_template.scale_to(k)

    @override
    def instantiate(
        self, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        """Generate the numpy array representing the template.

        Args:
            plaquette_indices: the plaquette indices that will be forwarded to
                the underlying Shape instance's instantiate method. Defaults
                to `range(1, self.expected_plaquettes_number + 1)` if `None`.

        Returns:
            a numpy array with the given plaquette indices arranged according to
            the underlying shape of the template.
        """
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))

        ret = numpy.zeros(self.shape.to_numpy_shape(), dtype=numpy.int_)
        ishape = self._tiled_template.shape

        for i, row in enumerate(self._grid):
            for j, offset in enumerate(row):
                # Here, an offset of 0 means "no template here", so we do not
                # have anything to do.
                if offset == 0:
                    continue
                template_expected_plaquettes_num = (
                    self._tiled_template.expected_plaquettes_number
                )
                plaquette_offset = template_expected_plaquettes_num * (offset - 1)
                plaquette_indices = list(
                    range(
                        plaquette_offset + 1,
                        plaquette_offset + template_expected_plaquettes_num + 1,
                    )
                )
                ret[
                    i * ishape.y : (i + 1) * ishape.y, j * ishape.x : (j + 1) * ishape.x
                ] = self._tiled_template.instantiate(plaquette_indices)
        return ret

    @property
    @override
    def scalable_shape(self) -> Scalable2D:
        """Returns a scalable version of the template shape."""
        base_shape = self._tiled_template.scalable_shape
        return Scalable2D(self._cols * base_shape.x, self._rows * base_shape.y)

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        """Returns the number of plaquettes expected from the `instantiate`
        method.

        Returns:
            the number of plaquettes expected from the `instantiate` method.
        """
        return self._tiled_template.expected_plaquettes_number * max(
            self._sorted_indices_in_grid
        )

    @override
    def get_plaquette_indices_on_sides(self, _: list[TemplateSide]) -> list[int]:
        """Get the indices of plaquettes that are located on the provided
        sides.

        Args:
            sides: the sides to recover plaquettes from.

        Returns:
            a non-ordered list of plaquette numbers.
        """
        raise NotImplementedError()