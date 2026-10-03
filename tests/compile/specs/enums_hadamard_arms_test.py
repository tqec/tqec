"""Tests for Hadamard-arm tracking on spatial cubes (issue #840).

These tests verify that ``CubeSpec`` correctly records which spatial arms
carry a Hadamard transition, so that the fixed-bulk convention can emit
corner plaquettes consistently (split-colour vs normal extended-stabiliser
triangles) instead of relying on the "left-right arm drops corners"
workaround that will break once left-right Hadamards exist.
"""

from __future__ import annotations

import pytest

from tqec.compile.specs.base import CubeSpec
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def _spatial_cube_graph_with_pipes(
    hadamard_pipes: set[str] | None = None,
) -> tuple[BlockGraph, object]:
    """Build a 2x2 spatial-cube block graph with one pipe per direction.

    The central cube is a ZZX spatial cube connected to four neighbours
    (UP/RIGHT/DOWN/LEFT). Pipes whose name is in ``hadamard_pipes`` carry a
    Hadamard transition.

    Returns:
        (graph, central_cube)

    """
    hadamard_pipes = hadamard_pipes or set()
    g = BlockGraph("Test Hadamard Arms")
    centre = g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("zzx"))
    # Four neighbours in the spatial plane.
    up = g.add_cube(Position3D(0, -1, 0), ZXCube.from_str("zzx"))
    right = g.add_cube(Position3D(1, 0, 0), ZXCube.from_str("zzx"))
    down = g.add_cube(Position3D(0, 1, 0), ZXCube.from_str("zzx"))
    left = g.add_cube(Position3D(-1, 0, 0), ZXCube.from_str("zzx"))
    # Y-direction pipes for UP/DOWN, X-direction pipes for LEFT/RIGHT.
    for direction, (cube_a, cube_b) in {
        "up": (centre, up),
        "down": (centre, down),
        "left": (centre, left),
        "right": (centre, right),
    }.items():
        base_kind = "xoz" if direction in ("up", "down") else "oxz"
        pipe_kind = PipeKind.from_str(base_kind + ("H" if direction in hadamard_pipes else ""))
        g.add_pipe(cube_a, cube_b, pipe_kind)
    return g, g[centre]


@pytest.mark.parametrize(
    ("hadamard_directions", "expected"),
    [
        (set(), SpatialArms.NONE),
        ({"up"}, SpatialArms.UP),
        ({"right"}, SpatialArms.RIGHT),
        ({"down"}, SpatialArms.DOWN),
        ({"left"}, SpatialArms.LEFT),
        ({"up", "down"}, SpatialArms.UP | SpatialArms.DOWN),
        ({"left", "right"}, SpatialArms.LEFT | SpatialArms.RIGHT),
        ({"up", "left"}, SpatialArms.UP | SpatialArms.LEFT),
    ],
)
def test_from_hadamard_pipes_in_graph(
    hadamard_directions: set[str], expected: SpatialArms
) -> None:
    graph, centre = _spatial_cube_graph_with_pipes(hadamard_directions)
    arms = SpatialArms.from_hadamard_pipes_in_graph(centre, graph)
    assert arms == expected


def test_from_hadamard_pipes_in_graph_non_spatial_cube() -> None:
    g = BlockGraph("Non-Spatial")
    cube_pos = g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("xzz"))
    assert SpatialArms.from_hadamard_pipes_in_graph(g[cube_pos], g) == SpatialArms.NONE


def test_cube_spec_from_cube_records_hadamard_arms() -> None:
    graph, centre = _spatial_cube_graph_with_pipes({"left", "down"})
    spec = CubeSpec.from_cube(centre, graph)
    assert spec.spatial_arms == (
        SpatialArms.UP | SpatialArms.RIGHT | SpatialArms.DOWN | SpatialArms.LEFT
    )
    assert spec.hadamard_arms == SpatialArms.LEFT | SpatialArms.DOWN


def test_cube_spec_without_hadamard_arms_has_none() -> None:
    graph, centre = _spatial_cube_graph_with_pipes(set())
    spec = CubeSpec.from_cube(centre, graph)
    assert spec.hadamard_arms == SpatialArms.NONE


def test_hadamard_arms_are_spatial_arms_subset() -> None:
    """A Hadamard arm that is not a spatial arm must be rejected."""
    with pytest.raises(TQECError):
        CubeSpec(ZXCube.from_str("xzz"), SpatialArms.NONE, SpatialArms.UP)
    with pytest.raises(TQECError):
        CubeSpec(ZXCube.from_str("xzz"), SpatialArms.UP, SpatialArms.RIGHT)


def test_hadamard_arms_requires_spatial_cube() -> None:
    """Hadamard arms on a non-spatial cube must be rejected."""
    with pytest.raises(TQECError):
        CubeSpec(ZXCube.from_str("xzz"), SpatialArms.NONE, SpatialArms.UP)


def test_hadamard_arms_equality_and_hash() -> None:
    """CubeSpec with same fields (incl. hadamard_arms) must be equal."""
    a = CubeSpec(ZXCube.from_str("zzx"), SpatialArms.UP, SpatialArms.UP)
    b = CubeSpec(ZXCube.from_str("zzx"), SpatialArms.UP, SpatialArms.UP)
    c = CubeSpec(ZXCube.from_str("zzx"), SpatialArms.UP, SpatialArms.NONE)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
