"""Helper functions for representing correlation surfaces in COLLADA model."""

import collada
import numpy as np
import numpy.typing as npt

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.correlation import CorrelationSurface, ZXEdge
from tqec.utils.enums import Basis
from tqec.interop.collada.read_write import _Transformation
from tqec.utils.position import Direction3D, FloatPosition3D, Position3D

TransformationResult = tuple[Basis, _Transformation]


class CorrelationSurfaceTransformationHelper:
    def __init__(self, block_graph: BlockGraph, pipe_length: float):
        """Helper class to compute transformations for representing correlation
        surfaces in a COLLADA model."""
        self.block_graph = block_graph
        self.pipe_length = pipe_length
        self.position_map = block_graph.to_zx_graph().positions

    def get_transformations_for_correlation_surface(
        self,
        correlation_surface: CorrelationSurface,
    ) -> list[TransformationResult]:
        """Compute the list of transformations (with corresponding bases) that
        represent each piece of the given correlation surface in the COLLADA
        model."""
        transformations: list[TransformationResult] = []

        # Surfaces in the pipes
        for edge in correlation_surface.span:
            if edge.is_self_loop():
                continue
            transformations.extend(self._compute_pipe_transformations(edge))

        # Surfaces in the cubes
        for v in correlation_surface.span_vertices():
            cube = self._get_cube(v)
            # Do not add surfaces in ports or Y-cubes
            if cube.is_port or cube.is_y_cube:
                continue
            transformations.extend(
                self._compute_cube_transformations(
                    v,
                    correlation_surface.edges_at(v),
                    correlation_surface.bases_at(v),
                )
            )
        return transformations

    def _get_position(self, v: int) -> Position3D:
        return self.position_map[v]

    def _get_cube(self, v: int) -> Cube:
        return self.block_graph[self.position_map[v]]

    def _edge_direction(self, edge: ZXEdge) -> Direction3D:
        """Return the edge direction."""
        p1, p2 = self._get_position(edge.u.id), self._get_position(edge.v.id)
        if p1.x != p2.x:
            return Direction3D.X
        if p1.y != p2.y:
            return Direction3D.Y
        return Direction3D.Z

    def _surface_normal_direction(
        self,
        correlation_edge: ZXEdge,
    ) -> Direction3D:
        """Get the correlation surface normal direction in the pipe."""
        u, v = correlation_edge
        up, vp = self._get_position(u.id), self._get_position(v.id)
        pipe = self.block_graph.get_pipe(up, vp)
        correlation_basis = u.basis
        return next(
            d
            for d in Direction3D.all_directions()
            if pipe.kind.get_basis_along(d) == correlation_basis.flipped()
        )

    def _scale_position(self, pos: Position3D) -> FloatPosition3D:
        return FloatPosition3D(*(p * (1 + self.pipe_length) for p in pos.as_tuple()))

    def _compute_pipe_transformations(self, edge: ZXEdge) -> list[TransformationResult]:
        transformations: list[TransformationResult] = []
        normal_direction = self._surface_normal_direction(edge)
        edge_direction = self._edge_direction(edge)

        # Compute the translation for the surface.
        base_position = self._get_position(edge.u.id)
        scaled_position = self._scale_position(base_position)
        surface_position = scaled_position.shift_in_direction(
            edge_direction, 1
        ).shift_in_direction(normal_direction, 0.5)
        rotation = _rotation_to_plane(normal_direction)
        scale_factor = self.pipe_length / 2 if edge.has_hadamard else self.pipe_length
        scale_direction = (
            edge_direction if edge_direction != Direction3D.Z else normal_direction
        )
        scale = _get_scale(scale_direction, scale_factor)

        transformations.append(
            (
                edge.u.basis,
                _Transformation(
                    translation=surface_position.as_array(),
                    rotation=rotation,
                    scale=scale,
                ),
            )
        )
        if edge.has_hadamard:
            transformations.append(
                (
                    edge.v.basis,
                    _Transformation(
                        translation=surface_position.shift_in_direction(
                            edge_direction, self.pipe_length / 2
                        ).as_array(),
                        rotation=rotation,
                        scale=scale,
                    ),
                ),
            )
        return transformations

    def _compute_cube_transformations(
        self,
        v: int,
        correlation_edges: set[ZXEdge],
        surface_bases: set[Basis],
    ) -> list[TransformationResult]:
        cube = self._get_cube(v)
        kind = cube.kind
        assert isinstance(kind, ZXCube)
        scaled_pos = self._scale_position(cube.position)
        transformations: list[TransformationResult] = []

        # Surfaces with even parity constraint
        if kind.normal_basis in surface_bases:
            assert len(correlation_edges) in {2, 4}, "Even parity constraint violated"
            if len(correlation_edges) == 2:
                e1, e2 = sorted(correlation_edges)
                # passthrough
                if self._edge_direction(e1) == self._edge_direction(e2):
                    normal_direction = self._surface_normal_direction(e1)
                    translation = scaled_pos.shift_in_direction(normal_direction, 0.5)
                    transformations.append(
                        (
                            kind.normal_basis,
                            _Transformation(
                                translation=translation.as_array(),
                                rotation=_rotation_to_plane(normal_direction),
                                scale=np.ones(3, dtype=np.float32),
                            ),
                        )
                    )
                # turn at corner
                else:
                    transformations.append(
                        self._compute_turn_transformation(scaled_pos, v, e1, e2)
                    )
            else:
                e1, e2, e3, e4 = sorted(correlation_edges)
                transformations.append(
                    self._compute_turn_transformation(scaled_pos, v, e1, e2)
                )
                transformations.append(
                    self._compute_turn_transformation(scaled_pos, v, e3, e4)
                )

        # Surfaces that can broadcast to all the neighbors
        if len(correlation_edges) == 2 or kind.normal_basis not in surface_bases:
            translation = scaled_pos.shift_in_direction(kind.normal_direction, 0.5)
            transformations.append(
                (
                    kind.normal_basis.flipped(),
                    _Transformation(
                        translation=translation.as_array(),
                        scale=np.ones(3, dtype=np.float32),
                        rotation=_rotation_to_plane(kind.normal_direction),
                    ),
                )
            )
        return transformations

    def _compute_turn_transformation(
        self,
        cube_pos: FloatPosition3D,
        v: int,
        e1: ZXEdge,
        e2: ZXEdge,
    ) -> TransformationResult:
        e1_direction = self._edge_direction(e1)
        e2_direction = self._edge_direction(e2)
        assert e1_direction != e2_direction
        corner_normal_direction = (
            set(Direction3D.all_directions()) - {e1_direction, e2_direction}
        ).pop()

        # whether the surface is "/" or "\" shape in the corner
        slash_shape = (e1.u.id == v) ^ (e2.u.id == v)
        angle = 45.0 if slash_shape else -45.0

        if corner_normal_direction != Direction3D.Z:
            corner_plane_x = (
                Direction3D.X
                if corner_normal_direction == Direction3D.Y
                else Direction3D.Y
            )
            corner_plane_y = Direction3D.Z
            rotation = _rotation_matrix(corner_normal_direction, angle)
        else:
            corner_plane_x, corner_plane_y = Direction3D.X, Direction3D.Y
            # First rotate to the XZ-plane, then rotate around the Z-axis
            first_rotation = _rotation_to_plane(Direction3D.Y)
            second_rotation = _rotation_matrix(Direction3D.Z, angle)
            rotation = second_rotation @ first_rotation
        scale = _get_scale(corner_plane_x, np.sqrt(2) / 2)
        if e1_direction == corner_plane_x:
            translation = cube_pos.shift_in_direction(corner_plane_y, 0.5)
        elif slash_shape:
            translation = cube_pos.shift_in_direction(corner_plane_x, 0.5)
        else:
            translation = cube_pos.shift_in_direction(
                corner_plane_x, 0.5
            ).shift_in_direction(corner_plane_y, 1.0)

        cube_kind = self._get_cube(v).kind
        assert isinstance(cube_kind, ZXCube)

        return (
            cube_kind.normal_basis,
            _Transformation(
                translation=translation.as_array(),
                rotation=rotation,
                scale=scale,
            ),
        )


def _rotation_to_plane(
    plane_normal_direction: Direction3D,
) -> npt.NDArray[np.float32]:
    """Starting from a surface in the XY-plane, rotate to the given plane."""
    if plane_normal_direction == Direction3D.Z:
        return _rotation_matrix(Direction3D.Z, 0.0)
    elif plane_normal_direction == Direction3D.X:
        return _rotation_matrix(Direction3D.Y, 90.0)
    else:
        return _rotation_matrix(Direction3D.X, 90.0)


def _rotation_matrix(
    axis: Direction3D,
    angle: float = 90.0,
) -> npt.NDArray[np.float32]:
    if axis == Direction3D.Y:
        angle = -angle
    axis_vec = np.zeros(3, dtype=np.float32)
    axis_vec[axis.value] = 1.0
    return np.asarray(
        collada.scene.RotateTransform(*axis_vec, angle=angle).matrix[:3, :3],
        dtype=np.float32,
    )


def _get_scale(
    scale_direction: Direction3D, scale_factor: float
) -> npt.NDArray[np.float32]:
    scale = np.ones(3, dtype=np.float32)
    scale[scale_direction.value] = scale_factor
    return scale
