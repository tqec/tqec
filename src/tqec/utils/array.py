import numpy
import numpy.typing as npt

from tqec.utils.exceptions import TQECError


def to2dlist(array: npt.NDArray[numpy.int_]) -> list[list[int]]:
    """Transform a 2D numpy array into a 2D array using Python list."""
    if len(array.shape) != 2:
        raise TQECError(f"Cannot transform a {len(array.shape)}-dimensional array to 2D.")
    return [[int(v) for v in line] for line in array]
