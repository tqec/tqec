"""Defines transformations used across TQEC interops folders."""

from tqec.utils.position import FloatPosition3D, Position3D
from tqec.utils.scale import round_or_fail


# TRANSFORMATIONS
def int_position_before_scale(pos: FloatPosition3D, pipe_length: float) -> Position3D:
    """Exchanges a float-based position with an integer-based position considering length of pipes.

    File reading functions recover the integer position via int_position_before_scale (atol=0.35)
    tolerance absorbs the 0.5/(1+pipe_length) residual for all pipe_length values usable in a 3D
    GUI (assume `pipe_length` >= 0.5, implies residual <= 0.333, so tolerance is 0.35.

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
    """Shift Y half-cube by +-0.5 in Z direction for visual rendering in DAE files.

    When writing visual files like COLLADA, pipe_direction is deduced by relative pos to neighbor.
    It shifts pos by 0.5 * pipe_direction along Z to place Y half-cube flush to pipe.
    For collada writer. +1 shifts Y half cube toward pipe above (init), -1 toward pipe below (meas).
    the pipe below (meas). The 0.5 equals one cube half-width in file space and is correct for
    all pipe_length values if component geometry is always 1x1x1 regardless of pipe spacing.

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
        pipe_length: the length of the pipes in the model. ``pipe_length`` is a file-format coordinate scaling factor--it has no meaning inside the compiler. It serves for 3D tools (primarily ``SketchUp``) to store positions in a visual coordinate space where blocks are separated by visible pipe gaps.

    Returns:
        A scaled (x, y, z)  position.

    """
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
