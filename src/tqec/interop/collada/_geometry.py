"""Define the face geometries used in COLLADA models."""

from __future__ import annotations

from dataclasses import astuple, dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from tqec.computation.cube import YHalfCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.interop.color import TQECColor
from tqec.utils.enums import Basis
from tqec.utils.position import Direction3D, FloatPosition3D, SignedDirection3D

if TYPE_CHECKING:
    from tqec.computation.block_graph import BlockKind


@dataclass(frozen=True)
class Face:
    """A rectangle face in the 3d space.

    The axis of (width, height, normal_direction) is by the right-hand rule, i.e.
    (X, Y, Z) or (Y, Z, X) or (Z, X, Y).

    Attributes:
        color: The color of the face.
        width: The width of the face.
        height: The height of the face.
        normal_direction: The normal direction of the face, which is the direction
            of the axis that the face is perpendicular to.
        position: The position of the face in the 3D space.

    """

    color: TQECColor
    width: float
    height: float
    normal_direction: SignedDirection3D
    position: FloatPosition3D = field(default=FloatPosition3D(0.0, 0.0, 0.0))

    @staticmethod
    def get_triangle_indices() -> npt.NDArray[np.int_]:
        return np.array([0, 0, 2, 2, 1, 1, 2, 2, 0, 0, 3, 3], dtype=np.int_)

    def get_vertices(self) -> npt.NDArray[np.float64]:
        a3 = self.normal_direction.direction.value
        a1, a2 = (a3 + 1) % 3, (a3 + 2) % 3
        # rectangle vertices
        vertices_position = np.zeros((4, 3), dtype=np.float64)

        # Define rectangle vertices in the plane defined by axes a1 and a2
        vertices_position[:, a1] = [0, self.width, self.width, 0]
        vertices_position[:, a2] = [0, 0, self.height, self.height]
        # translate the rectangle
        vertices_position += np.asarray(astuple(self.position), dtype=np.float64)
        return vertices_position.flatten()

    def get_normal_vectors(self) -> npt.NDArray[np.float64]:
        normal = np.zeros(3, dtype=np.float64)
        ax3_index = self.normal_direction.direction.value
        normal[ax3_index] = 1 if self.normal_direction.towards_positive else -1
        return np.tile(normal, 4)

    def shift_by(self, dx: float, dy: float, dz: float) -> Face:
        return Face(
            self.color,
            self.width,
            self.height,
            self.normal_direction,
            self.position.shift_by(dx, dy, dz),
        )

    def with_negated_normal_direction(self) -> Face:
        return Face(
            self.color,
            self.width,
            self.height,
            -self.normal_direction,
            self.position,
        )


class BlockGeometries:
    """A collection of geometries of blocks."""

    def __init__(self) -> None:
        self.geometries: dict[BlockKind, list[Face]] = {}
        # 6 x/z cube blocks
        self._load_zx_cube_geometries()
        # 1 y half cube block
        self._load_y_cube_geometry()
        # 6 pipe blocks without H
        self._load_pipe_without_hadamard_geometries()
        # 6 pipe blocks with H
        self._load_pipe_with_hadamard_geometries()

    def get_geometry(
        self,
        kind: BlockKind,
        pop_faces_at_directions: frozenset[SignedDirection3D] = frozenset(),
    ) -> list[Face]:
        """Get the geometry of a block kind, possibly with some faces popped out."""
        faces = self.geometries[kind]
        return [face for face in faces if face.normal_direction not in pop_faces_at_directions]

    def _load_zx_cube_geometries(self) -> None:
        """Geometries for zxx, xzx, xxz, xzz, zxz, zzx cubes."""
        width, height = 1.0, 1.0
        for kind in ZXCube.all_kinds():
            faces: list[Face] = []
            for direction in Direction3D.all_directions():
                basis = kind.get_basis_along(direction)
                face = Face(
                    TQECColor(basis.value),
                    width,
                    height,
                    SignedDirection3D(direction, False),
                )
                faces.append(face)
                translation = [0.0, 0.0, 0.0]
                translation[direction.value] = 1.0
                faces.append(face.shift_by(*translation).with_negated_normal_direction())
            self.geometries[kind] = faces

    def _load_y_cube_geometry(self) -> None:
        """Geometry for the Y Half Cube."""
        faces: list[Face] = []
        for direction in Direction3D.all_directions():
            if direction == Direction3D.X:
                width, height = 1.0, 0.5
            elif direction == Direction3D.Y:
                width, height = 0.5, 1.0
            else:
                width, height = 1.0, 1.0
            face = Face(TQECColor.Y, width, height, SignedDirection3D(direction, False))
            faces.append(face)
            translation = [0.0, 0.0, 0.0]
            translation[direction.value] = 1.0 if direction != Direction3D.Z else 0.5
            faces.append(face.shift_by(*translation).with_negated_normal_direction())
        self.geometries[YHalfCube()] = faces

    def _load_pipe_without_hadamard_geometries(self) -> None:
        """Geometries for ozx, oxz, xoz, zox, xzo, zxo pipes."""
        for name in ["ozx", "oxz", "xoz", "zox", "xzo", "zxo"]:
            faces: list[Face] = []
            kind = PipeKind.from_str(name)
            for direction in Direction3D.all_directions():
                basis = kind.get_basis_along(direction)
                if basis is None:
                    continue
                if direction.value == (kind.direction.value - 1) % 3:
                    width, height = 2.0, 1.0
                else:
                    width, height = 1.0, 2.0
                face = Face(
                    TQECColor(basis.value),
                    width,
                    height,
                    SignedDirection3D(direction, False),
                )
                faces.append(face)
                translation = [0.0, 0.0, 0.0]
                translation[direction.value] = 1.0
                faces.append(face.shift_by(*translation).with_negated_normal_direction())
            self.geometries[kind] = faces

    def _load_pipe_with_hadamard_geometries(self) -> None:
        """Geometries for ozxh, oxzh, zoxh, xozh, zxoh, xzoh pipes."""

        def _get_face_position(shift_direction: Direction3D, shift: float) -> FloatPosition3D:
            tmp: list[float] = [0, 0, 0]
            tmp[shift_direction.value] = shift
            return FloatPosition3D(*tmp)

        for name in ["ozxh", "oxzh", "zoxh", "xozh", "zxoh", "xzoh"]:
            faces: list[Face] = []
            kind = PipeKind.from_str(name)
            for direction in Direction3D.all_directions():
                basis = kind.get_basis_along(direction)
                if basis is None:
                    continue
                if direction.value == (kind.direction.value - 1) % 3:
                    w1, h1 = 0.9, 1.0
                    w2, h2 = 0.2, 1.0
                    w3, h3 = 0.9, 1.0
                else:
                    w1, h1 = 1.0, 0.9
                    w2, h2 = 1.0, 0.2
                    w3, h3 = 1.0, 0.9
                normal_direction = SignedDirection3D(direction, False)
                face1 = Face(TQECColor(basis.value), w1, h1, normal_direction)
                face2 = Face(
                    TQECColor.H,
                    w2,
                    h2,
                    normal_direction,
                    _get_face_position(kind.direction, 0.9),
                )
                face3 = Face(
                    face1.color.with_zx_flipped(),
                    w3,
                    h3,
                    normal_direction,
                    _get_face_position(kind.direction, 1.1),
                )
                faces += [face1, face2, face3]
                translation = [0, 0, 0]
                translation[direction.value] = 1
                faces.extend(
                    face.shift_by(*translation).with_negated_normal_direction()
                    for face in [face1, face2, face3]
                )
            self.geometries[kind] = faces

    def _load_correlation_surface_geometries(self) -> None:
        """Geometries for horizontal, vertical and inclined surfaces."""
        # horizontal surface
        self.geometries  # pragma: no cover


def get_correlation_surface_geometry(basis: Basis) -> Face:
    """Get the face representing the correlation surface."""
    normal_direction = SignedDirection3D(Direction3D.Z, True)
    return Face(TQECColor(basis.value + "_CORRELATION"), 1.0, 1.0, normal_direction)
