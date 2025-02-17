"""Defines support operations needed to rotate 3D structures upon import to TQEC.

Enabling import of rotated 3D structures is convenient for small computations and
seemingly necessary for large computations. For a small computation, researchers can,
with some pain, rotate the structure back to the original axis or exchange any rotated
cubes if only part of the structure was rotated. But this becomes harder
as the size of the computation grows.

The following descriptions might aid clarity.

In COLLADA files, rotations DO NOT show as "degree" or "radian" rotations applied
to an fixed object. Instead, rotations are encoded directly into the a 4x4 transformation
matrix that looks as follows:
- POS: Position / Translation
- RT: Vector starting at POSITION and shooting RIGHT
- BK: Vector starting at POSITION and shooting BACKWARDS
- UP: Vector starting at POSITION and shooting UP
- US (let's ignore this – won't be using it here): Uniform scaling vector

[RT.x] [UP.x] [BK.x] [POS.x]
[RT.y] [UP.y] [BK.y] [POS.y]
[RT.z] [UP.z] [BK.z] [POS.Z]
[    ] [    ] [    ] [US   ]

The 3x3 submatrix containing RT, UP, BK information will be an identity matrix if object is unrotated.
Any rotation an user inputs in a software like SketchUp is applied by rotating this matrix algebraically.
As a result, it is possible to know how much a cube/pipe can be rotated by comparing its
transformation matrix against the original identity matrix (see notes in functions: !).

Additionally, since the names of blocks/pipes in TQEC are tied to the face of the unrotated blocks,
name equivalences can be calculated algebraically using the transformation matrix directly.

"""

import numpy as np
import numpy.typing as npt
from tqec.computation.block_graph import BlockKind
from tqec.utils.exceptions import TQECException

from tqec.computation.pipe import PipeKind
from tqec.computation.cube import YCube, ZXCube


def block_kind_from_str(string: str) -> BlockKind:
    """Parse a block kind from a string."""
    string = string.upper()
    if "O" in string:
        return PipeKind.from_str(string)
    elif string == "Y":
        return YCube()
    else:
        return ZXCube.from_str(string)


def calc_rotation_angles(M: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    """Calculates the rotation angles of the three row vectors of matrix (M) from the original X/Y/Z axis (given by an identity matrix)).

    Args:
        M: rotation matrix for node, extracted from `.dae` file.

    Returns:
        rotations: the rotation angle for each of the three vectors in M (see notes: !)
    """

    # Placeholder for results
    rotations = np.array([])

    # Define matrix for an unrotated object
    ID = np.identity(3, dtype=int)

    # Calculate rotations
    # ! I think that, technically, this should be done per column (aka column-major)
    # ! but this function is only to confirm rotation validity rather than to transform objects
    # ! per row (aka. row-major) is fine for this
    for i, row in enumerate(M):
        cos_theta = np.dot(ID[i], row) / (np.linalg.norm(ID[i]) * np.linalg.norm(row))
        angle_rad = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        angle_deg = np.degrees(angle_rad)
        rotations = np.append(rotations, [round(angle_deg)])

    return rotations


def get_axes_directions(rotate_matrix: npt.NDArray[np.float32]) -> dict[str, int]:
    """Gets up/down multipliers for each row of a rotation matrix.

    Args:
        rotate_matrix: rotation matrix for node.

    Returns:
        axes_directions: up/down multipliers for each axis
    """

    # Placeholder for results
    axes_directions = {"X": 1, "Y": 1, "Z": 1}

    # Loop builds dict with plus/minus direction for each axis
    for i, row in enumerate(rotate_matrix):
        axes_directions["XYZ"[i]] = -1 if sum(row) < 0 else 1

    return axes_directions


def rotate_block_kind_by_matrix(
    block_kind: BlockKind, rotate_matrix: npt.NDArray[np.float32]
) -> BlockKind:
    """Multiplies rotation matrix (rotate_matrix) with a symbolic vector made from the block_kind.
        - rotate_matrix is NOT rotated: block_kind untouched
        - rotate_matrix is rotated: block_kind rotated accordingly

    Args:
        rotate_matrix: rotation matrix for node.
        block_kind: original kind.

    Returns:
        rotated_kind: rotated kind for the node.
        axes_directions: up/down multipliers for each axis
    """

    # Placeholder for results
    rotated_name = ""

    # State cultivation blocks: special case – added chars needed to clear loop
    original_name = (
        str(block_kind)[:3] if len(str(block_kind)) > 1 else str(block_kind) + "-!"
    )

    # Loop:
    # - applies transformation encoded in rotate_matrix to vectorised kind
    # - builds dict with plus/minus direction for each axis
    for i, row in enumerate(rotate_matrix):
        entry = ""
        for j, element in enumerate(row):
            entry += abs(int(element)) * original_name[j]
        rotated_name += entry

    # Fails & re-writes for special blocks
    axes_directions = get_axes_directions(rotate_matrix)

    # Reject state cultivation blocks if rotated_name not ends in "!" or axes_directions["Z"] is negative
    if "!" in rotated_name and (
        not rotated_name.endswith("!") or axes_directions["Z"] < 0
    ):
        raise TQECException(
            f"There is an invalid rotation for {rotated_name.replace('!', '').replace('-', '')} block."
        )
    # Clean kind names for special names
    # State cultivation
    elif "!" in rotated_name:
        rotated_name = str(block_kind)
    # Hadamard
    elif "H" in str(block_kind):
        rotated_name += str(block_kind)[-1]

    # Re-write kind
    rotated_kind = block_kind_from_str(rotated_name)

    return rotated_kind
