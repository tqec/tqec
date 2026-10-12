import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.compile.specs.base import CubeSpec
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, LeafCubeKind, PatchRotationKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.patch_rotation import patch_rotation, spatially_aligned_patch_rotation
from tqec.interop.bgraph.read_write import read_bgraph, write_bgraph
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.scale import LinearFunction


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
    g.validate()


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
    g.validate()


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
    g.validate()


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
    g.validate()


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


def test_patch_rotation_graph_rotate_not_implemented() -> None:
    g = patch_rotation()
    with pytest.raises(
        NotImplementedError,
        match=r"Rotating a block graph containing patch rotation cubes is not implemented",
    ):
        g.rotate(Direction3D.Z)

    with pytest.raises(
        NotImplementedError,
        match=r"Rotating a block graph containing patch rotation cubes is not implemented",
    ):
        g.rotate(Direction3D.X)

    g_spat = spatially_aligned_patch_rotation()
    with pytest.raises(
        NotImplementedError,
        match=r"Rotating a block graph containing patch rotation cubes is not implemented",
    ):
        g_spat.rotate(Direction3D.Y)


def test_patch_rotation_validate_pipe_count() -> None:
    # 0 pipes
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), PatchRotationKind.PR)
    with pytest.raises(TQECError, match=r"Patch rotation cube .* does not have exactly two pipes"):
        g.validate()

    # 1 pipe
    g.add_cube(Position3D(0, 0, 0), LeafCubeKind.PORT, label="In")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), "ZXO")
    with pytest.raises(TQECError, match=r"Patch rotation cube .* does not have exactly two pipes"):
        g.validate()

    # 3 pipes
    g.add_cube(Position3D(0, 0, 2), LeafCubeKind.PORT, label="Out")
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2), "XZO")
    g.add_cube(Position3D(1, 0, 1), LeafCubeKind.PORT, label="Extra")
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1), "OZX")
    with pytest.raises(TQECError, match=r"Patch rotation cube .* does not have exactly two pipes"):
        g.validate()


def test_patch_rotation_validate_pipe_direction() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), LeafCubeKind.PORT, label="In")
    g.add_cube(Position3D(0, 0, 1), PatchRotationKind.PR)
    g.add_cube(Position3D(1, 0, 1), LeafCubeKind.PORT, label="Out")
    # One in Z direction, one in X direction
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), "ZXO")
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1), "OZX")
    with pytest.raises(
        TQECError,
        match=r"Patch rotation cube .* must connect two collinear pipes in the same direction",
    ):
        g.validate()


def test_patch_rotation_validate_wall_compatibility() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), LeafCubeKind.PORT, label="In")
    g.add_cube(Position3D(0, 0, 1), PatchRotationKind.PR)
    g.add_cube(Position3D(0, 0, 2), LeafCubeKind.PORT, label="Out")
    # Both pipes are ZXO (transverse wall bases X=Z and Y=X are unchanged, not swapped)
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), "ZXO")
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2), "ZXO")
    with pytest.raises(
        TQECError, match=r"Transverse wall bases must swap across the patch rotation cube"
    ):
        g.validate()


def test_patch_rotation_validate_y_axis() -> None:
    in_pos = Position3D(0, 0, 0)
    pr_pos = Position3D(0, 1, 0)
    out_pos = Position3D(0, 2, 0)

    # Valid Y-axis patch rotation:
    # Direction is Y (ortho: Z, X).
    # Pipe 1 (XOZ): at PR, Z=Basis.Z, X=Basis.X
    # Pipe 2 (ZOX): at PR, Z=Basis.X, X=Basis.Z (swapped!)
    g = BlockGraph("Y-aligned Patch Rotation")
    g.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g.add_cube(pr_pos, PatchRotationKind.PR)
    g.add_cube(out_pos, LeafCubeKind.PORT, label="Out")
    g.add_pipe(in_pos, pr_pos, PipeKind.from_str("XOZ"))
    g.add_pipe(pr_pos, out_pos, PipeKind.from_str("ZOX"))
    g.validate()

    # Invalid Y-axis patch rotation:
    g_invalid = BlockGraph("Invalid Y-aligned PR")
    g_invalid.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g_invalid.add_cube(pr_pos, PatchRotationKind.PR)
    g_invalid.add_cube(out_pos, LeafCubeKind.PORT, label="Out")
    g_invalid.add_pipe(in_pos, pr_pos, PipeKind.from_str("XOZ"))
    g_invalid.add_pipe(pr_pos, out_pos, PipeKind.from_str("XOZ"))
    with pytest.raises(
        TQECError, match=r"Transverse wall bases must swap across the patch rotation cube"
    ):
        g_invalid.validate()


def test_patch_rotation_validate_with_hadamard() -> None:
    in_pos = Position3D(0, 0, 0)
    pr_pos = Position3D(0, 0, 1)
    out_pos = Position3D(0, 0, 2)

    # Pipe 1 with Hadamard: ZXO with H (ZXOH).
    # At tail (PR face), X flips Z->X, Y flips X->Z.
    # So at PR face, Pipe 1 has X=X, Y=Z.
    # Therefore, Pipe 2 must have X=Z, Y=X at PR face.
    # Since Pipe 2 is at head, kind ZXO provides X=Z, Y=X.
    g = BlockGraph("PR with Hadamard")
    g.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g.add_cube(pr_pos, PatchRotationKind.PR)
    g.add_cube(out_pos, LeafCubeKind.PORT, label="Out")
    g.add_pipe(in_pos, pr_pos, PipeKind.from_str("ZXOH"))
    g.add_pipe(pr_pos, out_pos, PipeKind.from_str("ZXO"))
    g.validate()

    # If Pipe 2 is XZO instead, bases at PR face do not swap:
    g_invalid = BlockGraph("Invalid PR with Hadamard")
    g_invalid.add_cube(in_pos, LeafCubeKind.PORT, label="In")
    g_invalid.add_cube(pr_pos, PatchRotationKind.PR)
    g_invalid.add_cube(out_pos, LeafCubeKind.PORT, label="Out")
    g_invalid.add_pipe(in_pos, pr_pos, PipeKind.from_str("ZXOH"))
    g_invalid.add_pipe(pr_pos, out_pos, PipeKind.from_str("XZO"))
    with pytest.raises(
        TQECError, match=r"Transverse wall bases must swap across the patch rotation cube"
    ):
        g_invalid.validate()


def test_patch_rotation_to_zx_graph_not_implemented() -> None:
    g = patch_rotation()
    with pytest.raises(
        NotImplementedError,
        match=r"Conversion of patch rotation cube to PyZX vertex type and phase is not supported",
    ):
        g.to_zx_graph()

    with pytest.raises(
        NotImplementedError,
        match=r"Conversion of patch rotation cube to PyZX vertex type and phase is not supported",
    ):
        PositionedZX.from_block_graph(g)

    with pytest.raises(
        NotImplementedError,
        match=r"Conversion of patch rotation cube to PyZX vertex type and phase is not supported",
    ):
        g.find_correlation_surfaces()


@pytest.mark.parametrize("convention", [FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION])
def test_patch_rotation_compilation_not_implemented(convention) -> None:
    g = patch_rotation(Basis.Z)
    with pytest.raises(
        NotImplementedError,
        match=r"Compiling a block graph containing patch rotation cubes is not supported",
    ):
        compile_block_graph(g, convention=convention)

    with pytest.raises(
        NotImplementedError,
        match=r"Compiling a block graph containing patch rotation cubes is not supported",
    ):
        compile_block_graph(g, convention=convention, observables=None)


def test_patch_rotation_cube_builders_not_implemented() -> None:
    spec = CubeSpec(PatchRotationKind.PR)
    linear = LinearFunction(2, -1)

    bulk_builder = FIXED_BULK_CONVENTION.triplet.cube_builder
    with pytest.raises(
        NotImplementedError, match=r"Patch rotation cube compilation is not supported"
    ):
        bulk_builder(spec, linear)

    boundary_builder = FIXED_BOUNDARY_CONVENTION.triplet.cube_builder
    with pytest.raises(
        NotImplementedError, match=r"Patch rotation cube compilation is not supported"
    ):
        boundary_builder(spec, linear)

    # Ordinary cube compilation remains unaffected
    zx_spec = CubeSpec(ZXCube.from_str("ZXZ"))
    assert bulk_builder(zx_spec, linear) is not None
    assert boundary_builder(zx_spec, linear) is not None
