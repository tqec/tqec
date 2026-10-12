import os
import tempfile
from pathlib import Path

import collada
import numpy as np
import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import LeafCubeKind, PatchRotationKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.patch_rotation import patch_rotation, spatially_aligned_patch_rotation
from tqec.gallery.three_cnots import three_cnots
from tqec.interop.collada._geometry import (
    BlockGeometries,
    _get_template_dae_path,
    load_patch_rotation_meshes,
)
from tqec.interop.collada.read_write import _BaseColladaData
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D, SignedDirection3D


def rotated_cnot(observable_basis: Basis | None = None) -> BlockGraph:
    """Create a block graph for the logical CNOT gate.

    Args:
        observable_basis: The observable basis that the block graph can support.
            If None, the four ports of the block graph will be left open.
            Otherwise, the ports will be filled with the cubes that have the
            initializations and measurements in the given observable basis.

    Returns:
        A :py:class:`~tqec.computation.block_graph.BlockGraph` instance representing
        the logical CNOT gate.

    """
    g = BlockGraph()

    nodes = [
        (Position3D(0, 0, 1), "P", "In_Control"),
        (Position3D(0, 1, 1), "ZXX", ""),
        (Position3D(0, 2, 1), "ZZX", ""),
        (Position3D(0, 3, 1), "P", "Out_Control"),
        (Position3D(0, 1, 0), "ZXX", ""),
        (Position3D(0, 2, 0), "ZZX", ""),
        (Position3D(1, 0, 0), "P", "In_Target"),
        (Position3D(1, 1, 0), "ZZX", ""),
        (Position3D(1, 2, 0), "ZZX", ""),
        (Position3D(1, 3, 0), "P", "Out_Target"),
    ]

    for pos, kind, label in nodes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5), (5, 8), (6, 7), (7, 8), (8, 9)]

    for p0, p1 in pipes:
        g.add_pipe(nodes[p0][0], nodes[p1][0])

    if observable_basis == Basis.Z:
        g.fill_ports(ZXCube.from_str("ZZX"))
    elif observable_basis == Basis.X:
        g.fill_ports(ZXCube.from_str("ZXX"))
    return g


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_logical_cnot_collada_write_read(pipe_length: float) -> None:
    block_graph = cnot(Basis.X)

    # Set `delete=False` to be compatible with Windows
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph

    # Manually delete the temporary file
    os.remove(temp_file.name)


def test_rotated_cnot_collada_write_read() -> None:
    block_graph = rotated_cnot(Basis.Z)

    rotated_cnot_dae_path = Path(__file__).parent / "test_files/rotated_cnot.dae"
    block_graph_from_file = BlockGraph.from_dae_file(rotated_cnot_dae_path)

    assert block_graph_from_file == block_graph


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
def test_three_cnots_collada_write_read(pipe_length: float) -> None:
    block_graph = three_cnots(Basis.Z)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, pipe_length)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == block_graph
    os.remove(temp_file.name)


def test_open_ports_roundtrip_not_equal() -> None:
    block_graph = cnot()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        block_graph.to_dae_file(temp_file.name, 2.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file != block_graph
    os.remove(temp_file.name)


def test_y_cube_positioning_during_roundtrip() -> None:
    g = BlockGraph()
    u = g.add_cube(Position3D(0, 0, 0), "Y")
    v = g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(u, v)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        g.to_dae_file(temp_file.name, 10.0)
        block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
        assert block_graph_from_file == g
    os.remove(temp_file.name)


def test_collada_write_read_with_correlation_surface() -> None:
    block_graph = cnot(Basis.X)
    correlation_surfaces = block_graph.find_correlation_surfaces()

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        for correlation_surface in correlation_surfaces:
            block_graph.to_dae_file(
                temp_file.name,
                2.0,
                pop_faces_at_directions=("+X", "-Y"),
                show_correlation_surface=correlation_surface,
            )
            block_graph_from_file = BlockGraph.from_dae_file(temp_file.name)
            assert block_graph_from_file == block_graph

    os.remove(temp_file.name)


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 10.0])
@pytest.mark.parametrize("y_is_init", [True, False], ids=["init", "meas"])
def test_y_cube_init_meas_roundtrip(pipe_length: float, y_is_init: bool) -> None:
    """Y init (pipe above, +0.5 shift) and Y meas (pipe below, -0.5 shift) survive roundtrip."""
    g = BlockGraph()
    if y_is_init:
        g.add_cube(Position3D(0, 0, 0), "Y")
        g.add_cube(Position3D(0, 0, 1), "ZXX")
        g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    else:
        g.add_cube(Position3D(0, 0, 0), "ZXX")
        g.add_cube(Position3D(0, 0, 1), "Y")
        g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name, pipe_length)
        g2 = BlockGraph.from_dae_file(f.name)
    os.remove(f.name)
    assert g2 == g


def test_dae_roundtrip_preserves_y_cube_position_above_origin():
    """Y half cubes at z > 0 must survive a write -> read round-trip.

    Before this fix, offset_y_cube_position(pos, pipe_length) divided z by
    (1 + pipe_length) and int_position_before_scale(..., pipe_length) did so
    again, scaling Y cube z down by an extra factor of (1 + pipe_length).
    A Y at TQEC (1,1,3) landed at (1,1,1), colliding with any cube there.
    """
    g = BlockGraph()
    g.add_cube(Position3D(1, 1, 1), ZXCube.from_str("XZZ"))
    g.add_cube(Position3D(1, 1, 2), ZXCube.from_str("XZZ"))
    g.add_cube(Position3D(1, 1, 3), LeafCubeKind.Y_HALF_CUBE)
    g.add_pipe(Position3D(1, 1, 1), Position3D(1, 1, 2), PipeKind.from_str("XZO"))
    g.add_pipe(Position3D(1, 1, 2), Position3D(1, 1, 3), PipeKind.from_str("XZO"))

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        g2 = BlockGraph.from_dae_file(f.name)

    y_cubes = [c for c in g2.cubes if c.kind is LeafCubeKind.Y_HALF_CUBE]
    assert len(y_cubes) == 1
    assert y_cubes[0].position == Position3D(1, 1, 3)


def test_patch_rotation_collada_export() -> None:
    g = patch_rotation()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        mesh = collada.Collada(f.name)
        geom_ids = [geom.id for geom in mesh.geometries]
        assert "ID645" in geom_ids
        assert "ID651" in geom_ids
        assert "ID657" in geom_ids

        node_names = [n.name for n in mesh.nodes]
        assert "PR" in node_names
        pr_node = next(n for n in mesh.nodes if n.name == "PR")
        assert len(pr_node.children) == 3

        materials_by_geom = {
            c.geometry.id: [mn.target.id for mn in c.materials] for c in pr_node.children
        }
        assert materials_by_geom["ID645"] == ["X_material"]
        assert materials_by_geom["ID651"] == ["Z_material"]
        assert materials_by_geom["ID657"] == ["H_material"]
    os.remove(f.name)


def test_spatially_aligned_patch_rotation_collada_export() -> None:
    g = spatially_aligned_patch_rotation()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        mesh = collada.Collada(f.name)
        geom_ids = [geom.id for geom in mesh.geometries]
        assert "ID645" in geom_ids
        assert "ID651" in geom_ids
        assert "ID657" in geom_ids

        node_names = [n.name for n in mesh.nodes]
        assert "PR" in node_names
    os.remove(f.name)


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_patch_rotation_collada_write_read_roundtrip(obs_basis: Basis) -> None:
    g = patch_rotation(obs_basis)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        g2 = BlockGraph.from_dae_file(f.name)
        assert g2 == g
    os.remove(f.name)


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_spatially_aligned_patch_rotation_collada_write_read_roundtrip(obs_basis: Basis) -> None:
    g = spatially_aligned_patch_rotation(obs_basis)
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name)
        g2 = BlockGraph.from_dae_file(f.name)
        assert g2 == g
    os.remove(f.name)


def test_patch_rotation_pop_faces_not_implemented() -> None:
    g = patch_rotation()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        temp_file_name = f.name
    try:
        with pytest.raises(
            NotImplementedError,
            match=r"Popping faces at directions is not supported for PatchRotationKind\.PR",
        ):
            g.to_dae_file(temp_file_name, pop_faces_at_directions=["+X"])
    finally:
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)

    geometries = BlockGeometries()
    with pytest.raises(
        NotImplementedError,
        match=r"PatchRotationKind\.PR geometry is mesh-based",
    ):
        geometries.get_geometry(PatchRotationKind.PR)

    with pytest.raises(
        NotImplementedError,
        match=r"Popping faces at directions is not supported for PatchRotationKind\.PR",
    ):
        geometries.get_geometry(
            PatchRotationKind.PR,
            pop_faces_at_directions=frozenset([SignedDirection3D.from_string("+X")]),
        )

    base = _BaseColladaData()
    with pytest.raises(
        NotImplementedError,
        match=r"Popping faces at directions is not supported for PatchRotationKind\.PR",
    ):
        base.add_block_instance(
            np.eye(4, dtype=np.float32),
            PatchRotationKind.PR,
            [SignedDirection3D.from_string("+X")],
        )


def _get_node_world_bounds(node: collada.scene.Node) -> tuple[np.ndarray, np.ndarray]:
    """Calculate the min and max world-space coordinates of a node's geometries."""
    mat = node.matrix
    inst = node.children[0]
    lib_node = inst.node
    verts_list: list[np.ndarray] = []
    for c in lib_node.children:
        if hasattr(c, "geometry") and c.geometry.primitives:
            pts = np.asarray(c.geometry.primitives[0].vertex)
            homo = np.hstack([pts, np.ones((len(pts), 1))])
            world_pts = (homo @ mat.T)[:, :3]
            verts_list.append(world_pts)
    all_pts = np.concatenate(verts_list, axis=0)
    return all_pts.min(axis=0), all_pts.max(axis=0)


def test_patch_rotation_mesh_world_placement() -> None:
    g = patch_rotation()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name, pipe_length=2.0)
        mesh = collada.Collada(f.name)

    os.remove(f.name)
    nodes = {node.children[0].node.name: node for node in mesh.scene.nodes[0].children}

    pr_node = nodes["PR"]
    pr_det = float(np.linalg.det(pr_node.matrix[:3, :3]))
    assert pr_det > 0.0
    pr_min, pr_max = _get_node_world_bounds(pr_node)
    assert np.allclose(pr_min, [0.0, 0.0, 3.0], atol=1e-4)
    assert np.allclose(pr_max, [1.0, 1.0, 4.0], atol=1e-4)

    pipe1_node = nodes["ZXO"]
    p1_min, p1_max = _get_node_world_bounds(pipe1_node)
    assert np.allclose(p1_min, [0.0, 0.0, 1.0], atol=1e-4)
    assert np.allclose(p1_max, [1.0, 1.0, 3.0], atol=1e-4)

    pipe2_node = nodes["XZO"]
    p2_min, p2_max = _get_node_world_bounds(pipe2_node)
    assert np.allclose(p2_min, [0.0, 0.0, 4.0], atol=1e-4)
    assert np.allclose(p2_max, [1.0, 1.0, 6.0], atol=1e-4)

    # Pipes touch PR mesh exactly without gaps or overlaps
    assert np.isclose(p1_max[2], pr_min[2])
    assert np.isclose(pr_max[2], p2_min[2])


def test_spatially_aligned_patch_rotation_mesh_world_placement() -> None:
    g = spatially_aligned_patch_rotation()
    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name, pipe_length=2.0)
        mesh = collada.Collada(f.name)

    os.remove(f.name)
    nodes = {node.children[0].node.name: node for node in mesh.scene.nodes[0].children}

    pr_node = nodes["PR"]
    pr_det = float(np.linalg.det(pr_node.matrix[:3, :3]))
    assert pr_det > 0.0
    pr_min, pr_max = _get_node_world_bounds(pr_node)
    assert np.allclose(pr_min, [3.0, 0.0, 0.0], atol=1e-4)
    assert np.allclose(pr_max, [4.0, 1.0, 1.0], atol=1e-4)

    pipe1_node = nodes["OXZ"]
    p1_min, p1_max = _get_node_world_bounds(pipe1_node)
    assert np.allclose(p1_min, [1.0, 0.0, 0.0], atol=1e-4)
    assert np.allclose(p1_max, [3.0, 1.0, 1.0], atol=1e-4)

    pipe2_node = nodes["OZX"]
    p2_min, p2_max = _get_node_world_bounds(pipe2_node)
    assert np.allclose(p2_min, [4.0, 0.0, 0.0], atol=1e-4)
    assert np.allclose(p2_max, [6.0, 1.0, 1.0], atol=1e-4)

    # Pipes touch PR mesh exactly without gaps or overlaps
    assert np.isclose(p1_max[0], pr_min[0])
    assert np.isclose(pr_max[0], p2_min[0])


def test_y_aligned_patch_rotation_mesh_world_placement() -> None:
    g = BlockGraph("Y PR")
    g.add_cube(Position3D(0, 0, 0), LeafCubeKind.PORT, label="In")
    g.add_cube(Position3D(0, 1, 0), PatchRotationKind.PR)
    g.add_cube(Position3D(0, 2, 0), LeafCubeKind.PORT, label="Out")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 1, 0), "XOZ")
    g.add_pipe(Position3D(0, 1, 0), Position3D(0, 2, 0), "ZOX")

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
        g.to_dae_file(f.name, pipe_length=2.0)
        mesh = collada.Collada(f.name)

    os.remove(f.name)
    nodes = {node.children[0].node.name: node for node in mesh.scene.nodes[0].children}

    pr_node = nodes["PR"]
    pr_det = float(np.linalg.det(pr_node.matrix[:3, :3]))
    assert pr_det > 0.0
    pr_min, pr_max = _get_node_world_bounds(pr_node)
    assert np.allclose(pr_min, [0.0, 3.0, 0.0], atol=1e-4)
    assert np.allclose(pr_max, [1.0, 4.0, 1.0], atol=1e-4)


@pytest.mark.parametrize("pipe_length", [0.5, 1.0, 2.0, 5.0, 10.0])
def test_patch_rotation_various_pipe_lengths_roundtrip(pipe_length: float) -> None:
    for factory in [patch_rotation, spatially_aligned_patch_rotation]:
        g = factory(Basis.Z)
        with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as f:
            g.to_dae_file(f.name, pipe_length=pipe_length)
            g_read = BlockGraph.from_dae_file(f.name)
        os.remove(f.name)
        assert g_read == g


def test_template_dae_location() -> None:
    path = _get_template_dae_path()
    assert path.is_file()
    assert path.suffix == ".dae"
    meshes = load_patch_rotation_meshes()
    assert len(meshes) > 0


def test_template_dae_location_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    path = _get_template_dae_path()
    assert path.is_file()
