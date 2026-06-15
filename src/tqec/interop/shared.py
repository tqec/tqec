"""Defines transformations used across TQEC interops folders."""

import numpy as np

from tqec.utils.position import FloatPosition3D, Position3D
from tqec.utils.scale import round_or_fail


# TRANSFORMATIONS
def int_position_before_scale(pos: FloatPosition3D, pipe_length: float) -> Position3D:
    """Exchanges a float-based position with an integer-based position considering length of pipes.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model.

    Returns:
        An (x, y, z)  position where x, y, and z are integers.

    """
    return Position3D(
        x=round_or_fail(pos.x / (1 + pipe_length), atol=0.35),
        y=round_or_fail(pos.y / (1 + pipe_length), atol=0.35),
        z=round_or_fail(pos.z / (1 + pipe_length), atol=0.35),
    )


def offset_y_cube_position(pos: FloatPosition3D) -> FloatPosition3D:
    """Undo the writer's +0.5 z-shift for Y half cubes that had a pipe above.

    The DAE writer shifts a Y half cube's DAE z by +0.5 when there is a pipe
    directly above it, so that the upper-half geometry sits flush against the
    pipe. This helper detects that fractional z (z ≈ floor(z) + 0.5) and
    reverses the shift, leaving an integer DAE z that
    :func:`int_position_before_scale` then maps onto the TQEC grid.

    The previous signature took a ``pipe_length`` argument and divided z by
    ``(1 + pipe_length)``. That scaling was redundant with
    :func:`int_position_before_scale` and caused a double-scaling bug for any
    Y cube at z > 0.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.

    Returns:
        An offset (x, y, z)  position where x, y, and z are floats.

    """
    if np.isclose(pos.z - 0.5, np.floor(pos.z), atol=1e-9):
        pos = pos.shift_by(dz=-0.5)
    return FloatPosition3D(pos.x, pos.y, pos.z)


def scale_position(pos: Position3D, pipe_length: float = 0.0) -> FloatPosition3D:
    """Scale the position of a cube according to an arbitrary length of pipe.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model.

    Returns:
        A scaled (x, y, z)  position.

    """
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
