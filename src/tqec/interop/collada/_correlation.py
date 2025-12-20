"""Helper functions for representing correlation surfaces in COLLADA model."""

import collada
import numpy as np
import numpy.typing as npt

from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface, ZXEdge
from tqec.computation.cube import Cube, ZXCube
from tqec.interop.collada.read_write import _Transformation
from tqec.utils.enums import Basis
from tqec.utils.position import Direction3D, FloatPosition3D, Position3D

TransformationResult = tuple[Basis, _Transformation]


class CorrelationSurfaceTransformationHelper:
    def __init__(self, block_graph: BlockGraph, pipe_length: float):
        """Help computing transformations of correlation surfaces pieces in a :class:`.BlockGraph`.

        The correlation surface is decomposed into small pieces of surfaces that can be transformed
        from a single 1x1 square surface in the XY-plane. This class computes the transformations
        for each piece of the correlation surface.

        """
        self.block_graph = block_graph
        self.pipe_length = pipe_length
        self.position_map = block_graph.to_zx_graph().positions

    def get_transformations_for_correlation_surface(
        self,
        correlation_surface: CorrelationSurface,
    ) -> list[TransformationResult]:
        """Return the transformations representing each piece of the ``correlation_surface``."""
        transformations: list[TransformationResult] = []

        # Surfaces in the pipes
        for edge in correlation_surface.span:
            if edge.is_self_loop():
                continue
            transformations.extend(self._compute_pipe_transformations(edge))

        # Surfaces in the cubes
        for v in correlation_surface.span_vertices():
            cube = self._get_cube(v)
            # Do not add surfaces in ports or Y Half Cubes
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
        """Compute the surface transformations within a pipe.

        If the edge is a Hadamard edge, two surfaces with different basis are created.

        """
        transformations: list[TransformationResult] = []
        normal_direction = self._surface_normal_direction(edge)
        edge_direction = self._edge_direction(edge)

        # Compute the translation for the surface.
        base_position = self._get_position(edge.u.id)
        scaled_position = self._scale_position(base_position)
        surface_position = scaled_position.shift_in_direction(edge_direction, 1).shift_in_direction(
            normal_direction, 0.5
        )
        rotation = _rotation_to_plane(normal_direction)
        scale_factor = self.pipe_length / 2 if edge.has_hadamard else self.pipe_length
        scale_direction = edge_direction if edge_direction != Direction3D.Z else normal_direction
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
        """Compute the transformations for the surfaces in the cube."""
        cube = self._get_cube(v)
        kind = cube.kind
        assert isinstance(kind, ZXCube)
        scaled_pos = self._scale_position(cube.position)
        transformations: list[TransformationResult] = []

        # Surfaces with even parity constraint
        if kind.normal_basis in surface_bases:
            normal_basis_edges: set[ZXEdge] = set()
            for edge in correlation_edges:
                this_node = edge.u if edge.u.id == v else edge.v
                if this_node.basis == kind.normal_basis:
                    normal_basis_edges.add(edge)
            assert len(normal_basis_edges) in {2, 4}, "Even parity constraint violated"
            if len(normal_basis_edges) == 2:
                e1, e2 = sorted(normal_basis_edges)
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
                    transformations.extend(
                        self._compute_turn_transformation(scaled_pos, v, (e1, e2))
                    )
            else:
                e1, e2, e3, e4 = sorted(normal_basis_edges)
                transformations.extend(self._compute_turn_transformation(scaled_pos, v, (e1, e2)))
                transformations.extend(self._compute_turn_transformation(scaled_pos, v, (e3, e4)))

        # Surfaces that can broadcast to all the neighbors
        if len(surface_bases) == 2 or kind.normal_basis not in surface_bases:
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
        turn_edges: tuple[ZXEdge, ZXEdge],
    ) -> list[TransformationResult]:
        """Compute the transformations for the surfaces in a L-shape turn.

        At turn, two surfaces in the same basis are created and form a 90 degree angle.

        """
        cube_kind = self._get_cube(v).kind
        assert isinstance(cube_kind, ZXCube)

        transformations = []
        turn_dirs = [self._edge_direction(e) for e in turn_edges]
        for i, e in enumerate(turn_edges):
            d, other_d = turn_dirs[i], turn_dirs[1 - i]
            # scale transformation is applied before rotation and the primitive
            # surface is in the XY-plane, so we also need to scale in the XY-plane.
            scale_direction = d if d != Direction3D.Z else other_d
            scale = _get_scale(scale_direction, 0.5)
            rotation = _rotation_to_plane(other_d)
            translation = cube_pos.shift_in_direction(other_d, 0.5)
            if v == e.u.id:
                translation = translation.shift_in_direction(d, 0.5)
            transformations.append(
                (
                    cube_kind.normal_basis,
                    _Transformation(
                        translation=translation.as_array(),
                        rotation=rotation,
                        scale=scale,
                    ),
                )
            )
        return transformations


def _rotation_to_plane(
    plane_normal_direction: Direction3D,
) -> npt.NDArray[np.float32]:
    """Rotate a surface in the XY-plane to the given plane."""
    if plane_normal_direction == Direction3D.Z:
        return _rotation_matrix(Direction3D.Z, 0.0)
    elif plane_normal_direction == Direction3D.X:
        return _rotation_matrix(Direction3D.Y, 90.0)
    else:
        return _rotation_matrix(Direction3D.X, 90.0)  # pragma: no cover


def _rotation_matrix(
    axis: Direction3D,
    angle: float = 90.0,
) -> npt.NDArray[np.float32]:
    if axis == Direction3D.Y:
        angle = -angle
    axis_vec = np.zeros(3, dtype=np.float32)
    axis_vec[axis.value] = 1.0
    return np.asarray(
        collada.scene.RotateTransform(axis_vec[0], axis_vec[1], axis_vec[2], angle).matrix[:3, :3],
        dtype=np.float32,
    )


def _get_scale(scale_direction: Direction3D, scale_factor: float) -> npt.NDArray[np.float32]:
    scale = np.ones(3, dtype=np.float32)
    scale[scale_direction.value] = scale_factor
    return scale
