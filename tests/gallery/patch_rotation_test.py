import pytest

from tqec.computation.cube import Cube, PatchRotationKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.patch_rotation import patch_rotation, spatially_aligned_patch_rotation
from tqec.interop.bgraph.read_write import read_bgraph, write_bgraph
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def test_patch_rotation_kind() -> None:
    kind = PatchRotationKind.from_str("PR")
    assert kind is PatchRotationKind.PR
    assert str(kind) == "PR"

    with pytest.raises(TQECError, match=r"Unknown patch rotation kind string representation"):
        PatchRotationKind.from_str("INVALID")


def test_patch_rotation_cube() -> None:
    pos = Position3D(0, 0, 1)
    cube = Cube(pos, PatchRotationKind.PR)
    assert cube.is_patch_rotation
    assert not cube.is_zx_cube
    assert not cube.is_port
    assert not cube.is_y_cube
    assert not cube.is_conditional
    assert str(cube) == "PR(0,0,1)"

    cube_dict = cube.to_dict()
    assert cube_dict == {
        "position": (0, 0, 1),
        "kind": "PR",
        "label": "",
        "condition": None,
    }
    assert Cube.from_dict(cube_dict) == cube


def test_patch_rotation_open() -> None:
    g = patch_rotation()
    assert g.num_ports == 2
    assert g.num_cubes == 3
    assert g.num_pipes == 2
    assert {*g.ports.keys()} == {"In", "Out"}
    assert g.bounding_box_size() == (1, 1, 3)

    pr_cube = g[Position3D(0, 0, 1)]
    assert pr_cube.is_patch_rotation
    assert pr_cube.kind is PatchRotationKind.PR
    assert str(pr_cube.kind) == "PR"

    assert g.get_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1)).kind == PipeKind.from_str("ZXO")
    assert g.get_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2)).kind == PipeKind.from_str("XZO")


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_patch_rotation_filled(obs_basis: Basis) -> None:
    g = patch_rotation(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 3
    assert g.num_pipes == 2

    pr_cube = g[Position3D(0, 0, 1)]
    assert pr_cube.is_patch_rotation

    if obs_basis == Basis.Z:
        assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("ZXZ")
        assert g[Position3D(0, 0, 2)].kind == ZXCube.from_str("XZZ")
    else:
        assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("ZXX")
        assert g[Position3D(0, 0, 2)].kind == ZXCube.from_str("XZX")


def test_spatially_aligned_patch_rotation_open() -> None:
    g = spatially_aligned_patch_rotation()
    assert g.num_ports == 2
    assert g.num_cubes == 3
    assert g.num_pipes == 2
    assert {*g.ports.keys()} == {"In", "Out"}
    assert g.bounding_box_size() == (3, 1, 1)

    pr_cube = g[Position3D(1, 0, 0)]
    assert pr_cube.is_patch_rotation
    assert pr_cube.kind is PatchRotationKind.PR
    assert str(pr_cube.kind) == "PR"

    assert g.get_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0)).kind == PipeKind.from_str("OXZ")
    assert g.get_pipe(Position3D(1, 0, 0), Position3D(2, 0, 0)).kind == PipeKind.from_str("OZX")


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_spatially_aligned_patch_rotation_filled(obs_basis: Basis) -> None:
    g = spatially_aligned_patch_rotation(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 3
    assert g.num_pipes == 2

    pr_cube = g[Position3D(1, 0, 0)]
    assert pr_cube.is_patch_rotation

    if obs_basis == Basis.Z:
        assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("ZXZ")
        assert g[Position3D(2, 0, 0)].kind == ZXCube.from_str("ZZX")
    else:
        assert g[Position3D(0, 0, 0)].kind == ZXCube.from_str("XXZ")
        assert g[Position3D(2, 0, 0)].kind == ZXCube.from_str("XZX")


def test_patch_rotation_bgraph_round_trip() -> None:
    g = patch_rotation()
    bgraph_str = write_bgraph(g)
    assert ";PR;" in bgraph_str
    g_loaded = read_bgraph(bgraph_str)
    assert g_loaded.num_cubes == g.num_cubes
    assert g_loaded.num_pipes == g.num_pipes
    assert g_loaded[Position3D(0, 0, 1)].is_patch_rotation
    assert g_loaded.get_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1)).kind == PipeKind.from_str(
        "ZXO"
    )
    assert g_loaded.get_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2)).kind == PipeKind.from_str(
        "XZO"
    )


def test_spatially_aligned_patch_rotation_bgraph_round_trip() -> None:
    g = spatially_aligned_patch_rotation()
    bgraph_str = write_bgraph(g)
    assert ";PR;" in bgraph_str
    g_loaded = read_bgraph(bgraph_str)
    assert g_loaded.num_cubes == g.num_cubes
    assert g_loaded.num_pipes == g.num_pipes
    assert g_loaded[Position3D(1, 0, 0)].is_patch_rotation
    assert g_loaded.get_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0)).kind == PipeKind.from_str(
        "OXZ"
    )
    assert g_loaded.get_pipe(Position3D(1, 0, 0), Position3D(2, 0, 0)).kind == PipeKind.from_str(
        "OZX"
    )
