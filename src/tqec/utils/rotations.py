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
from scipy.spatial.transform import Rotation as R

from tqec.computation.block_graph import BlockKind, block_kind_from_str
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.scale import round_or_fail


def calc_rotation_angles(
    rotation_matrix: npt.NDArray[np.float32],
) -> npt.NDArray[np.float32]:
    """Calculates the rotation angles of the three row vectors of matrix (M) from the original X/Y/Z axis (given by an identity matrix)).

    Args:
        rotation_matrix: rotation matrix for node, extracted from `.dae` file.

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
    for i, row in enumerate(rotation_matrix):
        cos_theta = np.dot(ID[i], row) / (np.linalg.norm(ID[i]) * np.linalg.norm(row))
        angle_rad = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        angle_deg = np.degrees(angle_rad)
        rotations = np.append(rotations, [round(angle_deg)])

    return rotations


def get_axes_directions(rotation_matrix: npt.NDArray[np.float32]) -> dict[str, int]:
    """Gets up/down multipliers for each row of a rotation matrix.

    Args:
        rotation_matrix: rotation matrix for node.

    Returns:
        axes_directions: up/down multipliers for each axis
    """

    # Placeholder for results
    axes_directions = {"X": 1, "Y": 1, "Z": 1}

    # Loop builds dict with plus/minus direction for each axis
    for i, row in enumerate(rotation_matrix):
        axes_directions["XYZ"[i]] = -1 if sum(row) < 0 else 1

    return axes_directions


def rotate_block_kind_by_matrix(
    block_kind: BlockKind, rotation_matrix: npt.NDArray[np.float32]
) -> BlockKind:
    """Multiplies rotation matrix (rotate_matrix) with a symbolic vector made from the block_kind.
        - rotate_matrix is NOT rotated: block_kind untouched
        - rotate_matrix is rotated: block_kind rotated accordingly

    Args:
        rotation_matrix: rotation matrix for node.
        block_kind: original kind.

    Returns:
        rotated_kind: rotated kind for the node.
    """
    if str(block_kind) == "PORT":
        return block_kind

    # Placeholder for results
    rotated_name = ""

    # State cultivation blocks: special case – added chars needed to clear loop
    original_name = (
        str(block_kind)[:3] if len(str(block_kind)) > 1 else str(block_kind) + "-!"
    )

    # Loop:
    # - applies transformation encoded in rotate_matrix to vectorised kind
    for _, row in enumerate(rotation_matrix):
        entry = ""
        for j, element in enumerate(row):
            entry += abs(int(element)) * original_name[j]
        rotated_name += entry

    # Fails & re-writes for special blocks
    axes_directions = get_axes_directions(rotation_matrix)

    # Reject state cultivation blocks if rotated_name not ends in "!" or axes_directions["Z"] is negative
    if "!" in rotated_name and (
        not rotated_name.endswith("!") or axes_directions["Z"] < 0
    ):
        raise TQECException(
            f"There is an invalid rotation for {rotated_name.replace('!', '').replace('-', '')} block.",
            "Cultivation and Y blocks should only allow rotation around Z axis.",
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


def get_rotation_matrix(
    rotation_axis: Direction3D,
    counterclockwise: bool = True,
    angle: float = np.pi / 2,
) -> npt.NDArray[np.float32]:
    """Gets the rotation matrix for a given axis and rotation.

    Args:
        rotation_axis: axis to rotate around.
        counterclockwise: whether to rotate counterclockwise.
        angle: rotation angle in radians.

    Returns:
        The rotation matrix.
    """
    rot_vec = np.array([0, 0, 0])
    rot_vec[rotation_axis.value] = 1 if counterclockwise else -1
    return np.array(R.from_rotvec(rot_vec * angle).as_matrix(), dtype=np.float32)


def rotate_position_by_matrix(
    position: Position3D,
    rotation_matrix: npt.NDArray[np.float32],
) -> Position3D:
    """Rotates a cube by a given rotation matrix and returns the new position.

    Note that we rotate the position of the cube based on its center, while the
    position is based on its corner. Therefore, a cube at (0, 0, 0) rotated by
    90 degrees around the x-axis will be at (0, -1, 0).

    Args:
        position: cube position to rotate.
        rotation_matrix: rotation matrix.

    Returns:
        The rotated position.

    Raises:
        TQECException: if the rotated position is not integer.
    """
    rotation = R.from_matrix(rotation_matrix)
    center_pos = [i + 0.5 for i in position.as_tuple()]
    rotated_center = rotation.apply(center_pos)
    rotated_corner = [round_or_fail(i - 0.5) for i in rotated_center]
    return Position3D(*rotated_corner)
