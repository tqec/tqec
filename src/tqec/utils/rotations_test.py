from typing import TypedDict

import numpy as np
import numpy.typing as npt
from pytest import raises
import pytest

from tqec.utils.exceptions import TQECException
from tqec.computation.block_graph import block_kind_from_str
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.rotations import (
    calc_rotation_angles,
    get_axes_directions,
    get_rotation_matrix,
    rotate_block_kind_by_matrix,
    rotate_position_by_matrix,
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
        "rotate_matrix": np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]),
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
        "rotate_matrix": np.array([[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]),
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
        "rotate_matrix": np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]),
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
        rotated_kind = rotate_block_kind_by_matrix(kind, transformation["rotate_matrix"])
        assert str(rotated_kind) == transformation["rotated_kind"]


def test_invalid_y_rotations() -> None:
    with raises(TQECException):
        for transformation in invalid_y_rotations:
            kind = block_kind_from_str(transformation["kind"])
            rotate_block_kind_by_matrix(kind, transformation["rotate_matrix"])


@pytest.mark.parametrize(
    ("before_rotate", "axis", "n_half_pi", "counterclockwise", "after_rotate"),
    [
        (Position3D(0, 0, 0), Direction3D.X, 1, False, Position3D(0, 0, -1)),
        (Position3D(0, 0, 0), Direction3D.Y, 3, True, Position3D(-1, 0, 0)),
        (Position3D(1, 0, 0), Direction3D.Y, 1, True, Position3D(0, 0, -2)),
        (Position3D(3, 0, 1), Direction3D.Z, 2, True, Position3D(-4, -1, 1)),
        (Position3D(2, 3, 4), Direction3D.X, 3, False, Position3D(2, -5, 3)),
    ],
)
def test_rotate_position(
    before_rotate: Position3D,
    axis: Direction3D,
    n_half_pi: int,
    counterclockwise: bool,
    after_rotate: Position3D,
) -> None:
    rotation_matrix = get_rotation_matrix(axis, counterclockwise, n_half_pi * np.pi / 2)
    assert rotate_position_by_matrix(before_rotate, rotation_matrix) == after_rotate
