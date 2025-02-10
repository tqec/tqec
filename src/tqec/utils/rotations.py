"""Defines support operations needed to rotate 3D structures upon import to TQEC.

Enabling import of rotated 3D structures is convenient for small computations and
seemingly necessary for large computations. For a small computation, researchers can,
with some pain, rotate the structure back to the original axis or exchange any rotated
cubes if only part of the structure was rotated. But this becomes harder
as the size of the computation grows.


"""

import numpy as np
import numpy.typing as npt


def calc_rotation_angles(M: npt.NDArray) -> npt.NDArray:
    """Calculates the angle between the vectors of a matrix (M) and the vectors of identity matrix (ID).

    Args:
        M (np.ndarray): 3x3 matrix.

    Returns:
        rotations (np.ndarray): the rotation angle for each of the three vectors in M
    """
    rotations = np.array([])
    ID = np.identity(3, dtype=int)
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
        M (np.ndarray): rotation matrix for node, extracted from `.dae` file.
        name (string): original name of the node, extracted from `.dae` file.

    Returns:
        rotated_name (str): rotated name for the node.
        axes_directions (dict): up/down multipliers for each axis
    """

    rotated_name = ""
    axes_directions = {"X": 1, "Y": 1, "Z": 1}
    for i, row in enumerate(M):
        entry = ""
        for j, element in enumerate(row):
            entry += abs(int(element)) * name[j]
        axes_directions["XYZ"[i]] = -1 if sum(row) < 0 else 1
        rotated_name += entry
    return rotated_name, axes_directions
