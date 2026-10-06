import pathlib

import pytest
import pyzx as zx

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ConditionalCubeKind, PatchRotationKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.patch_rotation import patch_rotation, spatially_aligned_patch_rotation
from tqec.interop.bgraph.read_write import read_bgraph, write_bgraph
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D


def test_patch_rotation_kind() -> None:
    kind = PatchRotationKind.from_str("PR")
    assert kind is PatchRotationKind.PR
    assert str(kind) == "PR"

    with pytest.raises(TQECError, match=r"Unknown patch rotation kind string representation"):
        PatchRotationKind.from_str("INVALID")


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


@pytest.mark.parametrize("obs_basis", [None, Basis.X, Basis.Z])
def test_patch_rotation_validation(obs_basis: Basis | None) -> None:
    patch_rotation(obs_basis).validate()
    spatially_aligned_patch_rotation(obs_basis).validate()


def test_patch_rotation_validation_errors() -> None:
    # 1 pipe connected to PR
    g_one_pipe = BlockGraph()
    g_one_pipe.add_cube(Position3D(0, 0, 0), "P", "In")
    g_one_pipe.add_cube(Position3D(0, 0, 1), "PR", "")
    g_one_pipe.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), PipeKind.from_str("ZXO"))
    with pytest.raises(TQECError, match=r"does not have exactly two pipes connected"):
        g_one_pipe.validate()

    # Non-collinear pipes
    g_corner = BlockGraph()
    g_corner.add_cube(Position3D(0, 0, 0), "P", "In")
    g_corner.add_cube(Position3D(0, 0, 1), "PR", "")
    g_corner.add_cube(Position3D(1, 0, 1), "P", "Out")
    g_corner.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), PipeKind.from_str("ZXO"))
    g_corner.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1), PipeKind.from_str("OZX"))
    with pytest.raises(TQECError, match=r"must have collinear pipes"):
        g_corner.validate()

    # Collinear pipes that do not rotate transverse boundaries
    g_no_rot = BlockGraph()
    g_no_rot.add_cube(Position3D(0, 0, 0), "P", "In")
    g_no_rot.add_cube(Position3D(0, 0, 1), "PR", "")
    g_no_rot.add_cube(Position3D(0, 0, 2), "P", "Out")
    g_no_rot.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), PipeKind.from_str("ZXO"))
    g_no_rot.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2), PipeKind.from_str("ZXO"))
    with pytest.raises(TQECError, match=r"does not rotate patch boundaries"):
        g_no_rot.validate()


def test_patch_rotation_open_zx() -> None:
    c = zx.qasm("""qreg q[1];""")

    g1 = patch_rotation().to_zx_graph().g
    g1.set_inputs((0,))
    g1.set_outputs((2,))
    assert zx.compare_tensors(c, g1)

    g2 = spatially_aligned_patch_rotation().to_zx_graph().g
    g2.set_inputs((0,))
    g2.set_outputs((2,))
    assert zx.compare_tensors(c, g2)


@pytest.mark.parametrize(
    "obs_basis, num_surfaces, external_stabilizers",
    [
        (Basis.X, 1, {"XX"}),
        (Basis.Z, 1, {"ZZ"}),
        (None, 2, {"XX", "ZZ"}),
    ],
)
def test_patch_rotation_correlation_surfaces(
    obs_basis: Basis | None, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    for factory in [patch_rotation, spatially_aligned_patch_rotation]:
        g = factory(obs_basis)
        correlation_surfaces = g.find_correlation_surfaces()
        assert len(correlation_surfaces) == num_surfaces
        assert {
            s.external_stabilizer_on_graph(g) for s in correlation_surfaces
        } == external_stabilizers


def test_patch_rotation_dae_export(tmp_path: pathlib.Path) -> None:
    for factory in [patch_rotation, spatially_aligned_patch_rotation]:
        g = factory()
        viewer = g.view_as_html()
        assert len(viewer._repr_html_()) > 1000

        dae_file = tmp_path / f"{factory.__name__}.dae"
        g.to_dae_file(dae_file)
        g_imported = BlockGraph.from_dae_file(dae_file)
        assert g_imported.num_cubes == g.num_cubes
        assert g_imported.num_pipes == g.num_pipes


@pytest.mark.parametrize("axis", [Direction3D.X, Direction3D.Y, Direction3D.Z])
def test_patch_rotation_rotate(axis: Direction3D) -> None:
    for factory in [patch_rotation, spatially_aligned_patch_rotation]:
        g = factory()
        rotated = g.rotate(axis)
        assert rotated.num_cubes == g.num_cubes
        assert rotated.num_pipes == g.num_pipes
        assert any(cube.is_patch_rotation for cube in rotated.cubes)
        rotated.validate()


def test_patch_rotation_not_conditional_branch() -> None:
    with pytest.raises(
        TQECError, match=r"A patch rotation cannot be a branch of a conditional cube kind."
    ):
        ConditionalCubeKind((PatchRotationKind.PR, ZXCube.from_str("ZXZ")))  # type: ignore[arg-type]

    with pytest.raises(TQECError):
        ConditionalCubeKind.from_str("PR_ZXZ")
