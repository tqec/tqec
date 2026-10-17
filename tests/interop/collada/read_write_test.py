import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import LeafCubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery.cnot import cnot
from tqec.gallery.three_cnots import three_cnots
from tqec.interop.collada.read_write import read_block_graph_from_dae_file
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


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


def test_single_phase_multi_component_dae_imports_with_relative_placement() -> None:
    """Multi-component DAE with shared lattice phase should import preserving placement.

    Two disjoint structures placed on the same lattice phase can import as one graph,
    retaining their relative positions and distance.
    """
    # Build two separate components on the same lattice phase
    graph = BlockGraph("two_components")
    # Component 1: at (0, 0, 0)
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(1, 0, 0), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))

    # Component 2: at (5, 0, 0) - far enough to be distinct
    graph.add_cube(Position3D(5, 0, 0), "ZXZ")
    graph.add_cube(Position3D(5, 0, 1), "ZXX")
    graph.add_pipe(Position3D(5, 0, 0), Position3D(5, 0, 1))

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        graph.to_dae_file(temp_file.name, 2.0)
        # Import should succeed because all cubes share the same lattice phase
        imported = read_block_graph_from_dae_file(temp_file.name)
        assert imported == graph
        # Verify that components are still in place
        assert Position3D(0, 0, 0) in imported
        assert Position3D(5, 0, 0) in imported

    os.remove(temp_file.name)


def test_lattice_phase_mismatch_triggering_conditions() -> None:
    """Phase mismatch error is raised for independently placed structures in DAE.

    The phase check (_check_single_lattice_phase) verifies that all cubes align
    to a single lattice offset. When DAE files contain cubes that don't share
    one lattice phase (e.g., from SketchUp exports with independently placed
    structures), the error message clearly names the axis and suggests using
    split_components=True or split_dae_batch.
    """
    # disjoint_y_gadgets.dae contains eight Y-half-cube structures placed
    # independently in SketchUp, each with its own world-space translation.
    # This file cannot import as a whole because the inferred lattice offset
    # cannot account for all eight different placements simultaneously.
    dae_file = Path(__file__).parent / "test_files" / "disjoint_y_gadgets.dae"

    with pytest.raises(TQECError, match="do not share one lattice phase"):
        read_block_graph_from_dae_file(dae_file)

    # Verify the error message also suggests the correct solution
    try:
        read_block_graph_from_dae_file(dae_file)
    except TQECError as e:
        assert "split_components" in str(e)


def test_cube_collision_error_on_identical_lattice_positions() -> None:
    """Two cubes at identical lattice positions raise collision TQECError.

    When DAE parsing results in two cube instances at the same lattice position
    (e.g., from duplicated instance nodes at very close world coordinates),
    a TQECError is raised naming both world positions and the colliding
    lattice position.
    """
    # Create a DAE, then manually add a duplicate instance that will collide
    graph = BlockGraph("collision_demo")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        graph.to_dae_file(temp_file.name, 2.0)
        dae_path = temp_file.name

    try:
        # Parse and add a duplicate cube instance that maps to the same lattice
        tree = ET.parse(dae_path)
        root = tree.getroot()

        ns = {"c": root.tag.split("}")[0].strip("{")}
        scene = root.find(".//c:library_visual_scenes/c:visual_scene/c:node[@name='SketchUp']", ns)

        if scene is not None:
            # Find the first cube instance node and duplicate it
            cube_nodes = list(scene.findall("c:node", ns))
            if cube_nodes:
                orig_cube = cube_nodes[0]
                # Create a duplicate with slightly different position (within
                # the int_position_before_scale tolerance) that will map to the
                # same lattice position
                dup_cube = ET.fromstring(ET.tostring(orig_cube))
                dup_cube.attrib["id"] = dup_cube.attrib["id"] + "_dup"

                # Modify matrix: shift by 0.1 (within tolerance for rounding)
                for elem in dup_cube.iter():
                    if elem.tag.endswith("matrix"):
                        try:
                            matrix_str = (elem.text or "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1").strip()
                            vals = [float(x) for x in matrix_str.split()]
                            vals[12] += 0.1  # Shift x within rounding tolerance
                            elem.text = " ".join(str(v) for v in vals)
                        except (ValueError, IndexError):
                            pass
                        break

                scene.append(dup_cube)

        # Write modified DAE
        collision_path = tempfile.NamedTemporaryFile(suffix=".dae", delete=False).name
        tree.write(collision_path, encoding="utf-8", xml_declaration=True)

        # Attempt import - should raise collision error
        with pytest.raises(TQECError, match=r"same lattice position"):
            read_block_graph_from_dae_file(collision_path)

    finally:
        os.remove(dae_path)
        if "collision_path" in locals():
            os.remove(collision_path)


def test_aligned_structures_no_false_positives() -> None:
    """Properly aligned structures do not trigger phase or collision errors.

    Regression test: lattice-aligned cubes in different components should import
    without false positives from the phase or collision checks.
    """
    graph = BlockGraph("aligned")
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    graph.add_cube(Position3D(3, 0, 0), "ZXZ")  # Lattice aligned at spacing 3.0

    with tempfile.NamedTemporaryFile(suffix=".dae", delete=False) as temp_file:
        graph.to_dae_file(temp_file.name, 2.0)
        # This should import fine because both cubes are lattice-aligned
        imported = read_block_graph_from_dae_file(temp_file.name)
        assert len(imported.cubes) == 2

    os.remove(temp_file.name)
