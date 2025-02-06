# """Helper functions for representing correlation surfaces in COLLADA model."""
#
# import collada
# import numpy as np
# import numpy.typing as npt
#
# from tqec.computation.block_graph import BlockGraph
# from tqec.computation.cube import Cube, ZXCube
# from tqec.interop.pyzx.correlation import CorrelationSurface, ZXEdge, ZXNode
# from tqec.utils.enums import Basis
# from tqec.interop.collada.read_write import _Transformation
# from tqec.utils.position import Direction3D, FloatPosition3D, Position3D
#
#
# def get_transformations_for_correlation_surface(
#     block_graph: BlockGraph,
#     correlation_surface: CorrelationSurface,
#     pipe_length: float,
# ) -> list[tuple[str, _Transformation]]:
#     """Get the transformations of each piece of a correlation surface for
#     representing it in a COLLADA model."""
#     position_map = block_graph.to_zx_graph().positions
#     transformations: list[tuple[str, _Transformation]] = []
#     # Surfaces in the pipes
#     for edge in correlation_surface.span:
#         if edge.is_self_loop():
#             continue
#         transformations.extend(
#             _get_transformations_for_surface_in_pipe(
#                 block_graph, edge, pipe_length, position_map
#             )
#         )
#
#     # Surfaces in the cubes
#     for v in correlation_surface.span_vertices():
#         cube = block_graph[position_map[v]]
#         # Do not add surfaces in ports or Y-cubes
#         if cube.is_port or cube.is_y_cube:
#             continue
#         transformations.extend(
#             _get_transformations_for_surface_in_cube(
#                 block_graph,
#                 cube,
#                 correlation_surface.edges_at(v),
#                 node.kind,
#                 pipe_length,
#                 position_map,
#             )
#         )
#     return transformations
#
#
# def _get_transformations_for_surface_in_pipe(
#     block_graph: BlockGraph,
#     edge: ZXEdge,
#     pipe_length: float,
#     position_map: dict[int, Position3D],
# ) -> list[tuple[str, _Transformation]]:
#     transformations: list[tuple[str, _Transformation]] = []
#     normal_direction = _surface_normal_direction(block_graph, edge, position_map)
#     edge_direction = _edge_direction(edge, position_map)
#     surface_position = (
#         _scale_position(position_map[edge.u.id], pipe_length)
#         .shift_in_direction(edge_direction, 1)
#         .shift_in_direction(normal_direction, 0.5)
#     )
#     rotation = _rotation_to_plane(normal_direction)
#     scale = _get_scale(
#         edge_direction if edge_direction != Direction3D.Z else normal_direction,
#         pipe_length / 2 if edge.has_hadamard else pipe_length,
#     )
#     transformations.append(
#         (
#             edge.u.basis.value,
#             _Transformation(
#                 translation=surface_position.as_array(),
#                 rotation=rotation,
#                 scale=scale,
#             ),
#         )
#     )
#     if edge.has_hadamard:
#         transformations.append(
#             (
#                 edge.v.basis.value,
#                 _Transformation(
#                     translation=surface_position.shift_in_direction(
#                         edge_direction, pipe_length / 2
#                     ).as_array(),
#                     rotation=rotation,
#                     scale=scale,
#                 ),
#             ),
#         )
#     return transformations
#
#
# def _get_transformations_for_surface_in_cube(
#     block_graph: BlockGraph,
#     cube: Cube,
#     correlation_edges: set[ZXEdge],
#     correlation_bases: set[Basis],
#     pipe_length: float,
#     position_map: dict[int, Position3D],
# ) -> list[tuple[str, _Transformation]]:
#     scaled_pos = _scale_position(cube.position, pipe_length)
#     assert isinstance(cube.kind, ZXCube)
#     kind = cube.kind
#     transformations: list[tuple[str, _Transformation]] = []
#     # Surfaces with even parity constraint
#     if len(correlation_bases) == 2 or kind.normal_basis in correlation_bases:
#         assert len(correlation_edges) in {2, 4}, "Even parity constraint violated"
#         if len(correlation_edges) == 2:
#             e1, e2 = sorted(correlation_edges)
#             # passthrough
#             if _edge_direction(e1, position_map) == _edge_direction(e2, position_map):
#                 normal_direction = _surface_normal_direction(
#                     block_graph, e1, position_map
#                 )
#                 transformations.append(
#                     (
#                         kind.normal_basis.value,
#                         _Transformation(
#                             translation=scaled_pos.shift_in_direction(
#                                 normal_direction, 0.5
#                             ).as_array(),
#                             rotation=_rotation_to_plane(normal_direction),
#                             scale=np.ones(3, dtype=np.float32),
#                         ),
#                     )
#                 )
#             # turn at corner
#             else:
#                 transformations.append(
#                     _get_transformation_for_surface_at_turn(scaled_pos, node, e1, e2)
#                 )
#         else:
#             e1, e2, e3, e4 = sorted(correlation_edges)
#             transformations.append(
#                 _get_transformation_for_surface_at_turn(scaled_pos, node, e1, e2)
#             )
#             transformations.append(
#                 _get_transformation_for_surface_at_turn(scaled_pos, node, e3, e4)
#             )
#
#     # Surfaces that can broadcast to all the neighbors
#     if len(correlation_edges) == 2 or kind.normal_basis not in correlation_bases:
#         transformations.append(
#             (
#                 kind.normal_basis.flipped().value,
#                 _Transformation(
#                     translation=scaled_pos.shift_in_direction(
#                         kind.normal_direction, 0.5
#                     ).as_array(),
#                     scale=np.ones(3, dtype=np.float32),
#                     rotation=_rotation_to_plane(kind.normal_direction),
#                 ),
#             )
#         )
#     return transformations
#
#
# def _get_transformation_for_surface_at_turn(
#     cube_pos: FloatPosition3D,
#     node: ZXNode,
#     e1: ZXEdge,
#     e2: ZXEdge,
# ) -> tuple[ZXKind, _Transformation]:
#     assert e1.direction != e2.direction
#     corner_normal_direction = (
#         set(Direction3D.all_directions()) - {e1.direction, e2.direction}
#     ).pop()
#     # whether the surface is "/" or "\" shape in the corner
#     slash_shape = (e1.u == node) ^ (e2.u == node)
#     angle = 45.0 if slash_shape else -45.0
#
#     if corner_normal_direction != Direction3D.Z:
#         corner_plane_x = (
#             Direction3D.X if corner_normal_direction == Direction3D.Y else Direction3D.Y
#         )
#         corner_plane_y = Direction3D.Z
#         rotation = _rotation_matrix(corner_normal_direction, angle)
#     else:
#         corner_plane_x, corner_plane_y = Direction3D.X, Direction3D.Y
#         # First rotate to the XZ-plane, then rotate around the Z-axis
#         first_rotation = _rotation_to_plane(Direction3D.Y)
#         second_rotation = _rotation_matrix(Direction3D.Z, angle)
#         rotation = second_rotation @ first_rotation
#     scale = _get_scale(corner_plane_x, np.sqrt(2) / 2)
#     if e1.direction == corner_plane_x:
#         translation = cube_pos.shift_in_direction(corner_plane_y, 0.5)
#     elif slash_shape:
#         translation = cube_pos.shift_in_direction(corner_plane_x, 0.5)
#     else:
#         translation = cube_pos.shift_in_direction(
#             corner_plane_x, 0.5
#         ).shift_in_direction(corner_plane_y, 1.0)
#     return (
#         node.kind,
#         _Transformation(
#             translation=translation.as_array(),
#             rotation=rotation,
#             scale=scale,
#         ),
#     )
#
#
# def _scale_position(pos: Position3D, pipe_length: float) -> FloatPosition3D:
#     return FloatPosition3D(*(p * (1 + pipe_length) for p in pos.as_tuple()))
#
#
# def _rotation_to_plane(
#     plane_normal_direction: Direction3D,
# ) -> npt.NDArray[np.float32]:
#     """Starting from a surface in the XY-plane, rotate to the given plane."""
#     if plane_normal_direction == Direction3D.Z:
#         return _rotation_matrix(Direction3D.Z, 0.0)
#     elif plane_normal_direction == Direction3D.X:
#         return _rotation_matrix(Direction3D.Y, 90.0)
#     else:
#         return _rotation_matrix(Direction3D.X, 90.0)
#
#
# def _surface_normal_direction(
#     block_graph: BlockGraph,
#     correlation_edge: ZXEdge,
#     position_map: dict[int, Position3D],
# ) -> Direction3D:
#     """Get the correlation surface normal direction in the pipe."""
#     u, v = correlation_edge
#     up, vp = position_map[u.id], position_map[v.id]
#     pipe = block_graph.get_edge(up, vp)
#     correlation_basis = u.basis
#     return next(
#         d
#         for d in Direction3D.all_directions()
#         if pipe.kind.get_basis_along(d) == correlation_basis.flipped()
#     )
#
#
# def _rotation_matrix(
#     axis: Direction3D,
#     angle: float = 90.0,
# ) -> npt.NDArray[np.float32]:
#     if axis == Direction3D.Y:
#         angle = -angle
#     axis_vec = np.zeros(3, dtype=np.float32)
#     axis_vec[axis.value] = 1.0
#     return np.asarray(
#         collada.scene.RotateTransform(*axis_vec, angle=angle).matrix[:3, :3],
#         dtype=np.float32,
#     )
#
#
# def _get_scale(
#     scale_direction: Direction3D, scale_factor: float
# ) -> npt.NDArray[np.float32]:
#     scale = np.ones(3, dtype=np.float32)
#     scale[scale_direction.value] = scale_factor
#     return scale
#
#
# def _edge_direction(edge: ZXEdge, position_map: dict[int, Position3D]) -> Direction3D:
#     """Return the edge direction."""
#     p1, p2 = position_map[edge.u.id], position_map[edge.v.id]
#     if p1.x != p2.x:
#         return Direction3D.X
#     if p1.y != p2.y:
#         return Direction3D.Y
#     return Direction3D.Z
