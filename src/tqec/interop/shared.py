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
    """Encode or decode a Y half-cube position in file coordinate space.

    **Writer mode** (``pipe_direction`` provided): shift ``pos`` by
    ``0.5 * pipe_direction`` along Z using
    :meth:`.FloatPosition3D.shift_in_direction`, placing the Y half-cube flush
    against its connecting pipe.

    **Reader mode** (``pipe_direction`` is ``None``): undo the writer's ±0.5
    z-shift by rounding any half-integer z away from zero — positive
    half-integers round up (``ceil``), negative half-integers round down
    (``floor``) — recovering the logical integer position.

    Args:
        pos: position of the Y half-cube.
        pipe_direction: ``+1`` if the connecting pipe is at ``z+1`` (above),
            ``-1`` if it is at ``z-1`` (below), or ``None`` to decode (reader
            mode).

    Returns:
        In writer mode, ``pos`` shifted ±0.5 along Z.
        In reader mode, ``pos`` with z rounded away from zero when z is a
        half-integer; otherwise ``pos`` unchanged.

    """
    if pipe_direction is not None:
        return pos.shift_in_direction(Direction3D.Z, 0.5 * pipe_direction)
    frac = pos.z - np.floor(pos.z)
    if np.isclose(frac, 0.5, atol=1e-9):
        z_logical = np.ceil(pos.z) if pos.z > 0 else np.floor(pos.z)
        return FloatPosition3D(pos.x, pos.y, float(z_logical))
    return pos


def scale_position(pos: Position3D, pipe_length: float = 0.0) -> FloatPosition3D:
    """Scale the position of a cube according to an arbitrary length of pipe.

    Args:
        pos: (x, y, z) position where x, y, and z are floats.
        pipe_length: the length of the pipes in the model.

    Returns:
        A scaled (x, y, z)  position.

    """
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
