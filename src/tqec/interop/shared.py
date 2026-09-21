"""Defines transformations used across TQEC interops folders."""

from tqec.utils.position import FloatPosition3D, Position3D
from tqec.utils.scale import round_or_fail


# TRANSFORMATIONS
def int_position_before_scale(pos: FloatPosition3D, pipe_length: float) -> Position3D:
    """Exchanges a float-based position with an integer-based position considering length of pipes.

    The ``atol=0.35`` tolerance absorbs the ``0.5/(1+pipe_length)`` residual for all
    ``pipe_length`` values usable in a 3D GUI. Assuming ``pipe_length >= 0.5``, the
    residual is at most 0.333, so ``atol=0.35`` is sufficient.

    See the discussion about visual scaling in tqec/tqec#864 for more context.

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


def offset_y_half_cube_position(pos: FloatPosition3D, pipe_direction: int) -> FloatPosition3D:
    """Shift a Y half-cube by ±0.5 along Z for visual rendering in DAE files.

    Used in the collada writer. ``+1`` shifts toward the pipe above (init Y cube),
    ``-1`` shifts toward the pipe below (meas Y cube). The offset 0.5 equals one
    cube half-width in file space and is correct for all ``pipe_length`` values
    because cube geometry is always 1x1x1 regardless of pipe spacing.

    See tqec/tqec#939 and the discussion about visual scaling in tqec/tqec#864 for more context.

    Args:
        pos: (x, y, z) DAE-space position of the Y half-cube.
        pipe_direction: +1 for init (pipe above), -1 for meas (pipe below).

    Returns:
        The position shifted by 0.5 * pipe_direction along Z.

    """
    return pos.shift_by(dz=0.5 * pipe_direction)


def scale_position(pos: Position3D, pipe_length: float = 0.0) -> FloatPosition3D:
    """Scale the position of a cube according to an arbitrary length of pipe.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model. ``pipe_length`` is a
            file-format coordinate scaling factor with no meaning inside the compiler.
            It serves for 3D tools (primarily ``SketchUp``) to store positions in a
            visual coordinate space where blocks are separated by visible pipe gaps.

    Returns:
        A scaled (x, y, z)  position.

    """
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
