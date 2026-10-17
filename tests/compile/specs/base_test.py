import pytest

from tqec.compile.specs.base import CubeContext, CubeContextKey
from tqec.computation.block_graph import BlockGraph
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D, SignedDirection3D


def test_cube_context_neighbour_and_spatial_pipe():
    graph = BlockGraph()
    center_position = graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    right_position = graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(center_position, right_position)

    center = graph[center_position]
    right = graph[right_position]
    context = CubeContext(graph, center)

    assert context.neighbour(SignedDirection3D(Direction3D.X, True)) == right
    assert context.neighbour(SignedDirection3D(Direction3D.X, False)) is None
    assert context.has_spatial_pipe(SignedDirection3D(Direction3D.X, True))
    assert not context.has_spatial_pipe(SignedDirection3D(Direction3D.Y, True))


def test_cube_context_temporal_pipes_and_key():
    graph = BlockGraph()
    bottom_position = graph.add_cube(Position3D(0, 0, -1), "ZXZ")
    center_position = graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    top_position = graph.add_cube(Position3D(0, 0, 1), "ZXZ")

    graph.add_pipe(bottom_position, center_position)
    graph.add_pipe(center_position, top_position)

    center = graph[center_position]
    context = CubeContext(graph, center)

    assert context.has_temporal_pipe(False)
    assert context.has_temporal_pipe(True)
    assert context.key() == CubeContextKey(
        has_bottom_temporal_pipe=True,
        has_top_temporal_pipe=True,
    )


def test_cube_context_without_temporal_pipes():
    graph = BlockGraph()
    cube_position = graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    cube = graph[cube_position]
    context = CubeContext(graph, cube)

    assert not context.has_temporal_pipe(False)
    assert not context.has_temporal_pipe(True)
    assert context.key() == CubeContextKey(
        has_bottom_temporal_pipe=False,
        has_top_temporal_pipe=False,
    )


def test_cube_context_rejects_temporal_direction_as_spatial():
    graph = BlockGraph()
    cube_position = graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    context = CubeContext(graph, graph[cube_position])

    with pytest.raises(TQECError, match="spatial direction"):
        context.has_spatial_pipe(SignedDirection3D(Direction3D.Z, True))
