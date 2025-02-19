from typing import TypedDict

import numpy as np
import numpy.typing as npt
from pytest import raises

from tqec.utils.exceptions import TQECException
from tqec.computation.block_graph import block_kind_from_str
from tqec.utils.rotations import (
    calc_rotation_angles,
    get_axes_directions,
    rotate_block_kind_by_matrix,
)

rotation_matrices_for_testing = [
    np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]),  # x_90
    np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]),  # x_180
    np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]),  # x_270
    np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]),  # y_90
    np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]),  # y_180
    np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),  # y_270
    np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),  # z_90
    np.array([[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]),  # z_180
    np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),  # z_270
]

confirm_angles = [
    np.array([0.0, 90.0, 90.0]),  # x_90
    np.array([0.0, 180.0, 180.0]),  # x_180
    np.array([0.0, 90.0, 90.0]),  # x_270
    np.array([90.0, 0.0, 90.0]),  # y_90
    np.array([180.0, 0.0, 180.0]),  # y_180
    np.array([90.0, 0.0, 90.0]),  # y_270
    np.array([90.0, 90.0, 0.0]),  # z_90
    np.array([180.0, 180.0, 0.0]),  # z_180
    np.array([90.0, 90.0, 0.0]),  # z_270
]

confirm_directions = [
    {"X": 1, "Y": -1, "Z": 1},  # x_90
    {"X": 1, "Y": -1, "Z": -1},  # x_180
    {"X": 1, "Y": 1, "Z": -1},  # x_270
    {"X": 1, "Y": 1, "Z": -1},  # y_90
    {"X": -1, "Y": 1, "Z": -1},  # y_180
    {"X": -1, "Y": 1, "Z": 1},  # y_270
    {"X": -1, "Y": 1, "Z": 1},  # z_90
    {"X": -1, "Y": -1, "Z": 1},  # z_180
    {"X": 1, "Y": -1, "Z": 1},  # z_270
]


class RotDict(TypedDict):
    rotate_matrix: npt.NDArray[np.float32]
    kind: str
    rotated_kind: str


valid_rotations: list[RotDict] = [
    {
        "rotate_matrix": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]),
        "kind": "ZXO",
        "rotated_kind": "ZOX",
    },
    {
        "rotate_matrix": np.array(
            [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
        ),
        "kind": "ZOX",
        "rotated_kind": "ZOX",
    },
    {
        "rotate_matrix": np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),
        "kind": "ZXO",
        "rotated_kind": "OXZ",
    },
    {
        "rotate_matrix": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]),
        "kind": "XZOH",
        "rotated_kind": "XOZH",
    },
    {
        "rotate_matrix": np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),
        "kind": "XZO",
        "rotated_kind": "OZX",
    },
    {
        "rotate_matrix": np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),
        "kind": "Y",
        "rotated_kind": "Y",
    },
    {
        "rotate_matrix": np.array(
            [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
        ),
        "kind": "Y",
        "rotated_kind": "Y",
    },
    {
        "rotate_matrix": np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),
        "kind": "Y",
        "rotated_kind": "Y",
    },
]

invalid_y_rotations: list[RotDict] = [
    {
        "rotate_matrix": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]),
        "kind": "Y",
        "rotated_kind": "Y",
    },
    {
        "rotate_matrix": np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),
        "kind": "Y",
        "rotated_kind": "Y",
    },
    {
        "rotate_matrix": np.array(
            [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
        ),
        "kind": "Y",
        "rotated_kind": "Y",
    },
    {
        "rotate_matrix": np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]),
        "kind": "Y",
        "rotated_kind": "Y",
    },
]


def test_calc_rotation_angles() -> None:
    for i, M in enumerate(rotation_matrices_for_testing):
        R = calc_rotation_angles(M)
        assert R.all() == confirm_angles[i].all()


def test_get_axes_directions() -> None:
    for i, M in enumerate(rotation_matrices_for_testing):
        R = get_axes_directions(M)
        assert R == confirm_directions[i]


def test_rotate_block_kind() -> None:
    for transformation in valid_rotations:
        kind = block_kind_from_str(transformation["kind"])
        rotated_kind = rotate_block_kind_by_matrix(
            kind, transformation["rotate_matrix"]
        )
        assert str(rotated_kind) == transformation["rotated_kind"]


def test_invalid_y_rotations() -> None:
    with raises(TQECException):
        for transformation in invalid_y_rotations:
            kind = block_kind_from_str(transformation["kind"])
            rotate_block_kind_by_matrix(kind, transformation["rotate_matrix"])
