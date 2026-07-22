import math

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.computation.cube import (
    ConditionalCubeKind,
    Cube,
    LeafCubeKind,
    ZXCube,
    cube_kind_from_string,
)
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.rotations import get_rotation_matrix, rotate_block_kind_by_matrix

ZXZ_ZXX = ConditionalCubeKind((ZXCube.ZXZ, ZXCube.ZXX))


def _correlation_surface(u: Position3D, v: Position3D, basis: Basis) -> CorrelationSurface:
    return CorrelationSurface(frozenset({ZXEdge(ZXNode(u, basis), ZXNode(v, basis))}))


def _conditional_graph() -> BlockGraph:
    """Build a Z-memory column with a merged ancilla measured in a conditional basis.

    The condition is the parity of the first-round stabilizer measurements in the
    merged region (the "merge outcome" bit).
    """
    a0, a1 = Position3D(0, 0, 0), Position3D(0, 0, 1)
    b1, c = Position3D(1, 0, 1), Position3D(1, 0, 2)
    g = BlockGraph("conditional measurement")
    g.add_cube(a0, "ZXZ")
    g.add_cube(a1, "ZXZ")
    g.add_cube(b1, "ZXZ")
    g.add_cube(c, "ZXZ_ZXX", condition=_correlation_surface(a1, b1, Basis.X))
    g.add_pipe(a0, a1)
    g.add_pipe(a1, b1)
    g.add_pipe(b1, c)
    return g


def test_conditional_cube_kind_resolve() -> None:
    assert ZXZ_ZXX.branches == (ZXCube.ZXZ, ZXCube.ZXX)
    assert ZXZ_ZXX.resolve(0) == ZXCube.ZXZ
    assert ZXZ_ZXX.resolve(1) == ZXCube.ZXX
    assert ZXZ_ZXX.resolve(True) == ZXCube.ZXX
    assert ZXZ_ZXX.pipe_direction == Direction3D.Z


def test_conditional_cube_kind_str_round_trip() -> None:
    for kind in [
        ZXZ_ZXX,
        ConditionalCubeKind((ZXCube.XZX, ZXCube.XZZ)),
        ConditionalCubeKind((ZXCube.ZXZ, ZXCube.XXZ)),
        ConditionalCubeKind((ZXCube.ZXX, LeafCubeKind.Y_HALF_CUBE)),
        ConditionalCubeKind((LeafCubeKind.Y_HALF_CUBE, ZXCube.ZXX)),
    ]:
        assert ConditionalCubeKind.from_str(str(kind)) == kind
        assert cube_kind_from_string(str(kind)) == kind
    assert str(ZXZ_ZXX) == "ZXZ_ZXX"
    assert str(ConditionalCubeKind((ZXCube.ZXX, LeafCubeKind.Y_HALF_CUBE))) == "ZXX_Y"
    # "Y_HALF_CUBE" contains underscores but is not a conditional kind.
    assert cube_kind_from_string("Y_HALF_CUBE") is LeafCubeKind.Y_HALF_CUBE
    with pytest.raises(TQECError, match="conditional cube kind string"):
        ConditionalCubeKind.from_str("ZXZ_ZXX_ZXZ")


def test_conditional_cube_kind_structural_validation() -> None:
    with pytest.raises(TQECError, match="must differ"):
        ConditionalCubeKind((ZXCube.ZXZ, ZXCube.ZXZ))
    with pytest.raises(TQECError, match="port cannot be a branch"):
        ConditionalCubeKind((ZXCube.ZXZ, LeafCubeKind.PORT))
    # The two ZX branches differ along more than one axis.
    with pytest.raises(TQECError, match="all but exactly one axis"):
        ConditionalCubeKind((ZXCube.ZXZ, ZXCube.XZX))
    # A spatial-pipe conditional kind is expressible: branches differ along x.
    spatial = ConditionalCubeKind((ZXCube.ZXZ, ZXCube.XXZ))
    assert spatial.pipe_direction == Direction3D.X
    # Y half cube branches are expressible and impose a temporal pipe.
    with_y = ConditionalCubeKind((ZXCube.ZXX, LeafCubeKind.Y_HALF_CUBE))
    assert with_y.pipe_direction == Direction3D.Z


def test_conditional_cube_kind_rotation_is_total() -> None:
    for axis in Direction3D.all_directions():
        matrix = get_rotation_matrix(axis, True, math.pi / 2)
        rotated = rotate_block_kind_by_matrix(ZXZ_ZXX, matrix)
        assert isinstance(rotated, ConditionalCubeKind)
    # Rotating a temporal conditional kind about a spatial axis gives a
    # spatial-pipe conditional kind.
    matrix = get_rotation_matrix(Direction3D.X, True, math.pi / 2)
    rotated = rotate_block_kind_by_matrix(ZXZ_ZXX, matrix)
    assert isinstance(rotated, ConditionalCubeKind)
    assert rotated.pipe_direction != Direction3D.Z


def test_conditional_cube_kind_with_y_branch_rotation() -> None:
    # A Y half cube branch only connects along the time (Z) axis, so a conditional
    # kind containing one may only be rotated about Z.
    y_conditional = ConditionalCubeKind((ZXCube.ZXX, LeafCubeKind.Y_HALF_CUBE))
    # Rotation about Z succeeds and stays a temporal-pipe conditional kind.
    matrix = get_rotation_matrix(Direction3D.Z, True, math.pi / 2)
    rotated = rotate_block_kind_by_matrix(y_conditional, matrix)
    assert isinstance(rotated, ConditionalCubeKind)
    assert rotated.pipe_direction == Direction3D.Z
    # Rotation about a spatial axis is undefined for the Y branch and is rejected
    # with a message naming the offending conditional kind.
    matrix = get_rotation_matrix(Direction3D.X, True, math.pi / 2)
    with pytest.raises(TQECError, match="Cannot rotate conditional cube kind"):
        rotate_block_kind_by_matrix(y_conditional, matrix)


def test_conditional_cube_requires_condition() -> None:
    with pytest.raises(TQECError, match="must have a specified condition"):
        Cube(Position3D(0, 0, 0), ZXZ_ZXX)
    with pytest.raises(TQECError, match="Only a conditional cube"):
        Cube(
            Position3D(0, 0, 0),
            ZXCube.ZXZ,
            condition=_correlation_surface(Position3D(0, 0, 0), Position3D(0, 0, 1), Basis.Z),
        )


def test_conditional_cube_condition_must_be_in_the_past() -> None:
    # A condition strictly in the past of the conditional cube is accepted.
    Cube(
        Position3D(0, 0, 1),
        ZXZ_ZXX,
        condition=_correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.X),
    )
    # A condition touching the conditional cube's own layer is rejected: the
    # branch-selecting measurements must complete before the conditional layer.
    with pytest.raises(TQECError, match="must be in the past"):
        Cube(
            Position3D(0, 0, 1),
            ZXZ_ZXX,
            condition=_correlation_surface(Position3D(0, 0, 0), Position3D(0, 0, 1), Basis.X),
        )
    # A condition in the future of the conditional cube is rejected.
    with pytest.raises(TQECError, match="must be in the past"):
        Cube(
            Position3D(0, 0, 1),
            ZXZ_ZXX,
            condition=_correlation_surface(Position3D(0, 0, 2), Position3D(1, 0, 2), Basis.X),
        )


def test_conditional_cube_resolve() -> None:
    condition = _correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.X)
    cube = Cube(Position3D(1, 0, 1), ZXZ_ZXX, condition=condition)
    assert cube.is_conditional
    resolved = cube.resolve(1)
    assert resolved.kind == ZXCube.ZXX
    assert resolved.position == cube.position
    assert resolved.condition is None
    static = Cube(Position3D(0, 0, 0), ZXCube.ZXZ)
    assert static.resolve(1) is static


def test_conditional_cube_dict_round_trip() -> None:
    condition = _correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.X)
    cube = Cube(Position3D(1, 0, 1), ZXZ_ZXX, condition=condition)
    assert Cube.from_dict(cube.to_dict()) == cube


def test_block_graph_json_round_trip_with_condition(tmp_path) -> None:
    g = _conditional_graph()
    assert BlockGraph.from_dict(g.to_dict()) == g
    path = tmp_path / "graph.json"
    g.to_json(path)
    loaded = BlockGraph.from_json(path, graph_name=g.name)
    assert loaded == g


def test_resolve_conditional_kinds() -> None:
    g = _conditional_graph()
    assert g.has_conditional_cubes
    assert len(g.conditional_cubes) == 1
    conditional_position = g.conditional_cubes[0].position
    for value, expected_kind in [(0, ZXCube.ZXZ), (1, ZXCube.ZXX)]:
        resolved = g.resolve_conditional_kinds(value)
        assert not resolved.has_conditional_cubes
        assert resolved[conditional_position].kind == expected_kind
        assert resolved.num_pipes == g.num_pipes
        resolved.validate()
    per_position = g.resolve_conditional_kinds({conditional_position: 1})
    assert per_position[conditional_position].kind == ZXCube.ZXX


def test_spacetime_volume_with_conditional_cubes() -> None:
    g = _conditional_graph()
    # An X/Z conditional cube is a full cube: it does not contribute half Y cubes.
    assert g.num_half_y_cubes == 0
    assert g.spacetime_volume == 4
    # A conditional cube with a Y half cube branch contributes the branch-averaged
    # number of half Y cubes.
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXX")
    g.add_cube(
        Position3D(0, 0, 1),
        "ZXX_Y",
        condition=_correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.Z),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    assert g.num_half_y_cubes == 0.5
    assert g.spacetime_volume == 1.75


def test_shift_by_preserves_condition() -> None:
    g = _conditional_graph()
    shifted = g.shift_by(dz=2)
    conditional = shifted.conditional_cubes[0]
    assert conditional.position == Position3D(1, 0, 4)
    assert conditional.condition is not None
    assert conditional.condition.positions == {Position3D(0, 0, 3), Position3D(1, 0, 3)}


def test_rotate_with_condition_raises() -> None:
    g = _conditional_graph()
    with pytest.raises(NotImplementedError, match="Rotating a block graph"):
        g.rotate(Direction3D.Z)


def test_validate_conditional_cube_pipes() -> None:
    condition = _correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.X)
    # No pipe at all.
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), "ZXZ_ZXX", condition=condition)
    with pytest.raises(TQECError, match="exactly one pipe"):
        g.validate()
    # A spatial pipe on a temporal conditional kind.
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), "ZXZ_ZXX", condition=condition)
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1), "OXZ")
    with pytest.raises(TQECError, match="non-timelike"):
        g.validate()
    # A temporal pipe whose walls do not match one of the branches.
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "XZZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ_ZXX", condition=condition)
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), "XZO")
    with pytest.raises(TQECError, match=r"mismatched\s+colors"):
        g.validate()


def test_validate_y_branch_conditional_cube() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXX")
    g.add_cube(
        Position3D(0, 0, 1),
        "ZXX_Y",
        condition=_correlation_surface(Position3D(0, 0, 0), Position3D(1, 0, 0), Basis.Z),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.validate()
