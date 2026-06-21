"""Defines transformations used across TQEC interops folders."""

import numpy as np

from tqec.utils.position import Direction3D, FloatPosition3D, Position3D
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


def offset_y_half_cube_position(
    pos: FloatPosition3D, pipe_direction: int | None = None
) -> FloatPosition3D:
    """Translate a Y half-cube position to or from file coordinate space.

    When writing to a file type with visual detail, like COLLADA, the ``pipe_direction`` can be deduced by the relative position of the Y half cube with its single neighboring cube. This function shifts the half cube ``pos`` by ``0.5 * pipe_direction`` along Z, placing the Y half-cube flush against its connecting pipe.

    When reading from a file, the ``pipe_direction`` is ``None`` and the cube kind is given. The half integer displacement field is not semantically necessary for the block graph data structure. This function undos the writer's ``0.5`` z-shift by rounding any half-integer z away from zero. By rounding positive half-integers up (``ceil``) and negative half-integers down
    (``floor``), we recover the integer value signifying macroscopic connectivity.

    Args:
        pos: position of the Y half-cube.
        pipe_direction: ``+1`` if the connecting pipe is at ``z+1`` (above),
            ``-1`` if it is at ``z-1`` (below), or ``None`` to decode (reader
            mode).

    Returns:
        In writer mode, ``pos`` shifted either plus or minus 0.5 along Z.
        In reader mode, ``pos`` with z rounded away from zero when z is a
        half-integer; otherwise ``pos`` unchanged.

    """
    # writer mode
    if pipe_direction is not None:
        # cube kind is Y basis initialization if ``pipe_direction`` is positive, and Y basis measurement otherwise
        return pos.shift_in_direction(Direction3D.Z, 0.5 * pipe_direction)
    frac = pos.z - np.floor(pos.z)

    # reader mode
    if np.isclose(frac, 0.5, atol=1e-9):
        z_macroscopic = np.ceil(pos.z) if pos.z > 0 else np.floor(pos.z)
        return FloatPosition3D(pos.x, pos.y, float(z_macroscopic))
    return pos


def scale_position(pos: Position3D, pipe_length: float = 0.0) -> FloatPosition3D:
    """Scale the position of a cube according to an arbitrary length of pipe.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model. ``pipe_length`` is a file-format coordinate scaling factor--it has no meaning inside the compiler. It serves for 3D tools (primarily ``SketchUp``) to store positions in a visual coordinate space where blocks are separated by visible pipe gaps.

    Returns:
        A scaled (x, y, z)  position.

    """
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
