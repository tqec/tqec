"""Helper functions for representing correlation surfaces in COLLADA model."""

import numpy as np
import numpy.typing as npt
import collada

from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import Cube, ZXBasis, ZXCube
from tqec.computation.zx_graph import ZXEdge, ZXKind, ZXNode
from tqec.interop.collada.read_write import _Transformation
from tqec.position import Direction3D, FloatPosition3D, Position3D


def get_transformations_for_correlation_surface(
    block_graph: BlockGraph,
    correlation_surface: CorrelationSurface,
    pipe_length: float,
) -> list[tuple[ZXKind, _Transformation]]:
    """Get the transformations of each piece of a correlation surface for
    representing it in a COLLADA model."""
    transformations: list[tuple[ZXKind, _Transformation]] = []
    # Surfaces in the pipes
    for edge in correlation_surface.span:
        transformations.extend(
            _get_transformations_for_surface_in_pipe(block_graph, edge, pipe_length)
        )

    # Surfaces in the cubes
    for node in correlation_surface.nodes:
        cube = block_graph[node.position]
        # Do not add surfaces in ports or Y-cubes
        if cube.is_port or cube.is_y_cube:
            continue
        transformations.extend(
            _get_transformations_for_surface_in_cube(
                block_graph,
                cube,
                correlation_surface,
                node.kind,
                pipe_length,
            )
        )
    return transformations


def _get_transformations_for_surface_in_pipe(
    block_graph: BlockGraph,
    edge: ZXEdge,
    pipe_length: float,
) -> list[tuple[ZXKind, _Transformation]]:
    transformations = []
    normal_direction = _surface_normal_direction(block_graph, edge)
    surface_position = (
        _scale_position(edge.u.position, pipe_length)
        .shift_in_direction(edge.direction, 1)
        .shift_in_direction(normal_direction, 0.5)
    )
    rotation = _rotation_to_plane(normal_direction)
    scale = _get_scale(
        edge.direction if edge.direction != Direction3D.Z else normal_direction,
        pipe_length / 2 if edge.has_hadamard else pipe_length,
    )
    transformations.append(
        (
            edge.u.kind,
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
                edge.v.kind,
                _Transformation(
                    translation=surface_position.shift_in_direction(
                        edge.direction, pipe_length / 2
                    ).as_array(),
                    rotation=rotation,
                    scale=scale,
                ),
            ),
        )
    return transformations


def _get_transformations_for_surface_in_cube(
    block_graph: BlockGraph,
    cube: Cube,
    correlation_surface: CorrelationSurface,
    correlation: ZXKind,
    pipe_length: float,
) -> list[tuple[ZXKind, _Transformation]]:
    pos = cube.position
    scaled_pos = _scale_position(pos, pipe_length)
    assert isinstance(cube.kind, ZXCube)
    cube_normal_direction = cube.kind.normal_direction
    node = cube.to_zx_node()
    transformations = []
    # Surfaces with even parity constraint
    if correlation == ZXKind.Y or node.kind == correlation:
        edges = {
            edge for edge in correlation_surface.span if any(n == node for n in edge)
        }
        assert len(edges) in {2, 4}, "Even parity constraint violated"
        if len(edges) == 2:
            e1, e2 = sorted(edges)
            # passthrough
            if e1.direction == e2.direction:
                normal_direction = _surface_normal_direction(block_graph, e1)
                transformations.append(
                    (
                        node.kind,
                        _Transformation(
                            translation=scaled_pos.shift_in_direction(
                                normal_direction, 0.5
                            ).as_array(),
                            rotation=_rotation_to_plane(normal_direction),
                            scale=np.ones(3, dtype=np.float32),
                        ),
                    )
                )
            # turn at corner
            else:
                transformations.append(
                    _get_transformation_for_surface_at_turn(scaled_pos, node, e1, e2)
                )
        else:
            e1, e2, e3, e4 = sorted(edges)
            transformations.append(
                _get_transformation_for_surface_at_turn(scaled_pos, node, e1, e2)
            )
            transformations.append(
                _get_transformation_for_surface_at_turn(scaled_pos, node, e3, e4)
            )

    # Surfaces that can broadcast to all the neighbors
    if node.kind != correlation:
        transformations.append(
            (
                node.kind.with_zx_flipped(),
                _Transformation(
                    translation=scaled_pos.shift_in_direction(
                        cube_normal_direction, 0.5
                    ).as_array(),
                    scale=np.ones(3, dtype=np.float32),
                    rotation=_rotation_to_plane(cube_normal_direction),
                ),
            )
        )
    return transformations


def _get_transformation_for_surface_at_turn(
    cube_pos: FloatPosition3D,
    node: ZXNode,
    e1: ZXEdge,
    e2: ZXEdge,
) -> tuple[ZXKind, _Transformation]:
    assert e1.direction != e2.direction
    corner_normal_direction = (
        set(Direction3D.all_directions()) - {e1.direction, e2.direction}
    ).pop()
    # whether the surface is "/" or "\" shape in the corner
    slash_shape = (e1.u == node) ^ (e2.u == node)
    angle = 45.0 if slash_shape else -45.0

    if corner_normal_direction != Direction3D.Z:
        corner_plane_x = (
            Direction3D.X if corner_normal_direction == Direction3D.Y else Direction3D.Y
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
    if e1.direction == corner_plane_x:
        translation = cube_pos.shift_in_direction(corner_plane_y, 0.5)
    elif slash_shape:
        translation = cube_pos.shift_in_direction(corner_plane_x, 0.5)
    else:
        translation = cube_pos.shift_in_direction(
            corner_plane_x, 0.5
        ).shift_in_direction(corner_plane_y, 1.0)
    return (
        node.kind,
        _Transformation(
            translation=translation.as_array(),
            rotation=rotation,
            scale=scale,
        ),
    )


def _scale_position(pos: Position3D, pipe_length: float) -> FloatPosition3D:
    return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))


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


def _surface_normal_direction(
    block_graph: BlockGraph,
    correlation_edge: ZXEdge,
) -> Direction3D:
    """Get the correlation surface normal direction in the pipe."""
    u, v = correlation_edge
    pipe = block_graph.get_edge(u.position, v.position)
    correlation_basis = ZXBasis(u.kind.value)
    return next(
        d
        for d in Direction3D.all_directions()
        if pipe.kind.get_basis_along(d) == correlation_basis.with_zx_flipped()
    )


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
