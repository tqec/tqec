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


def calc_rotation_angles(M: npt.NDArray) -> npt.NDArray:
    """Calculates the angle between the vectors of a matrix (M) and the vectors of identity matrix (ID).

    Args:
        M (array): 3x3 matrix.

    Returns:
        rotations (array): the rotation angle for each of the three vectors in M (see notes: !)
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


def symbolic_multiplication(M: npt.NDArray, name: str) -> tuple[str, dict[str, int]]:
    """Multiplies a numerical matrix (M) with a symbolic vector (passed as string).
        - M is NOT rotated: name remains untouched
        - M is rotated: name rotated accordingly

    Args:
        M (array): rotation matrix for node, extracted from `.dae` file.
        name (string): original name of the node, extracted from `.dae` file.

    Returns:
        rotated_name (str): rotated name for the node.
        axes_directions (dict): up/down multipliers for each axis
    """

    # Placeholder for results
    rotated_name = ""
    axes_directions = {"X": 1, "Y": 1, "Z": 1}

    # State cultivation blocks need additional characters to clear operation
    name = name if len(name) == 3 else name + "-!"

    # Loop:
    # - applies transformation encoded in M to vectorised name
    # - builds a dictionary with plus/minus direction for each axis
    for i, row in enumerate(M):
        entry = ""
        for j, element in enumerate(row):
            entry += abs(int(element)) * name[j]
        axes_directions["XYZ"[i]] = -1 if sum(row) < 0 else 1
        rotated_name += entry

    return rotated_name, axes_directions
