import os
import tempfile
from dataclasses import FrozenInstanceError

import pytest

from tests.interop.collada.read_write_test import rotated_cnot
from tqec.computation.block_graph import BlockGraph, ComponentBounds
from tqec.computation.cube import ConditionalCubeKind, Cube, CubeKind, LeafCubeKind, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery import cnot, memory
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D


def test_block_graph_construction() -> None:
    g = BlockGraph()
    assert len(g.cubes) == 0
    assert len(g.pipes) == 0
    assert g.spacetime_volume == 0


def test_block_graph_add_cube() -> None:
    g = BlockGraph()
    v = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    assert g.num_cubes == 1
    assert g.spacetime_volume == 1
    assert g[v].kind == ZXCube.from_str("ZXZ")
    assert v in g

    with pytest.raises(TQECError, match=r"Cube already exists at position .*"):
        g.add_cube(Position3D(0, 0, 0), "XZX")

    v = g.add_cube(Position3D(1, 0, 0), "PORT", "P")
    assert g.num_cubes == 2
    assert g.num_ports == 1
    assert g.spacetime_volume == 1
    assert g[v].is_port

    with pytest.raises(TQECError, match=r".* port with the same label .*"):
        g.add_cube(Position3D(10, 0, 0), "P", "P")


def test_block_graph_add_pipe() -> None:
    g = BlockGraph()
    with pytest.raises(TQECError, match=r"No cube at position .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(1, 0, 0),
        )
    u = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    v = g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_pipe(u, v)
    assert g.num_pipes == 1
    assert g.pipes[0].kind == PipeKind.from_str("ZXO")
    assert g.has_pipe_between(u, v)
    assert len(g.leaf_cubes) == 2
    assert g.get_degree(u) == 1
    assert len(g.pipes_at(u)) == 1

    with pytest.raises(TQECError, match=r".* already a pipe between .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        )

    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    with pytest.raises(TQECError, match=r"No pipe between .*"):
        g.get_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))


def test_remove_block() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXZ")
    n3 = g.add_cube(Position3D(1, 0, 1), "P", "Out")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    assert g.num_cubes == 3
    assert g.num_pipes == 2
    assert g.num_ports == 2
    g.remove_cube(n1)
    assert g.num_cubes == 2
    assert g.num_pipes == 1
    assert g.num_ports == 1
    assert "In" not in g.ports

    g.remove_pipe(n2, n3)
    assert g.num_cubes == 2
    assert g.num_pipes == 0
    assert g.num_ports == 1
    assert not g.is_single_connected()


def test_block_graph_validate_y_cube() -> None:
    g = BlockGraph()
    u = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    v = g.add_cube(Position3D(1, 0, 0), "Y")
    g.add_pipe(u, v)
    with pytest.raises(TQECError, match="has non-timelike pipes connected"):
        g.validate()

    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 1), "Y")
    with pytest.raises(TQECError, match="does not have exactly one pipe connected"):
        g.validate()
    n2 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n3 = g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    with pytest.raises(TQECError, match="does not have exactly one pipe connected"):
        g.validate()


def test_block_graph_validate_3d_corner() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "XZX")
    n3 = g.add_cube(Position3D(1, 0, 1), "Y")
    n4 = g.add_cube(Position3D(1, 1, 0), "P", "P")
    g.add_pipe(n1, n2)
    g.add_pipe(n2, n3)
    g.add_pipe(n2, n4, "XOZ")

    with pytest.raises(TQECError):
        g.validate()


def test_block_graph_validate_ignore_shadowed_faces() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "XXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "XXZ")
    n3 = g.add_cube(Position3D(-1, 0, 0), "XXZ")
    n4 = g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    g.add_pipe(n1, n4, "ZXO")
    g.validate()


def test_graph_shift() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    shifted = g.shift_by(dz=-1)
    assert shifted.num_cubes == 1
    assert shifted.cubes[0].position == Position3D(0, 0, 0)

    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, -1), ZXCube.from_str("ZXZ"))
    n2 = g.add_cube(Position3D(1, 0, -1), ZXCube.from_str("XZX"))
    n3 = g.add_cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    minz = min(cube.position.z for cube in g.cubes)
    shifted = g.shift_by(dz=-minz)
    assert shifted.num_cubes == 3
    assert shifted.num_pipes == 2
    assert {cube.position for cube in shifted.cubes} == {
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
        Position3D(0, 0, 1),
    }


def test_fill_ports() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "P", "in")
    g.add_cube(Position3D(1, 0, 0), "P", "out")
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0), "OZX")
    assert g.num_ports == 2
    assert g.num_cubes == 2

    g1 = g.clone()
    g1.fill_ports(ZXCube.from_str("XZX"))
    assert g1.num_ports == 0
    assert g1.num_cubes == 2

    g2 = g.clone()
    g2.fill_ports({"in": ZXCube.from_str("XZX")})
    assert g2.num_ports == 1
    assert g2.num_cubes == 2


def test_compose_graphs() -> None:
    g1 = BlockGraph("g1")
    n1 = g1.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g1.add_cube(Position3D(1, 0, 0), "P", "Out")
    g1.add_pipe(n1, n2, "OXZ")

    g2 = g1.clone()
    g2.name = "g2"
    g_composed = g1.compose(g2, "Out", "In")
    assert g_composed.name == "g1_composed_with_g2"
    assert g_composed.num_cubes == 3
    assert g_composed.num_ports == 2
    assert g_composed.ports == {"In": n1, "Out": Position3D(2, 0, 0)}
    assert g_composed[Position3D(1, 0, 0)].kind == ZXCube.from_str("ZXZ")


def test_single_connected() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    assert g.is_single_connected()

    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    assert not g.is_single_connected()

    g.add_pipe(n1, n2)
    assert g.is_single_connected()


def test_graph_rotation() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_pipe(n1, n2)
    rg = g.rotate(Direction3D.Z)
    assert str(rg[Position3D(-1, 0, 0)].kind) == "XZZ"
    assert str(rg[Position3D(-1, 1, 0)].kind) == "XZZ"
    assert str(rg.pipes[0].kind) == "XOZ"
    assert rg.rotate(Direction3D.Z, num_90_degree_rotation=3) == g

    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "Y")
    with pytest.raises(TQECError):
        g.rotate(Direction3D.X)
    rg = g.rotate(Direction3D.Z)
    assert Position3D(-1, 0, 0) in rg
    assert str(rg.cubes[0].kind) == "Y"


@pytest.mark.parametrize("obs_basis", [Basis.Z, Basis.X, None])
def test_cnot_graph_rotation(obs_basis: Basis | None) -> None:
    g = cnot(obs_basis)
    rg = g.rotate(Direction3D.X, False)

    rg_from_scratch = rotated_cnot(obs_basis)

    # We need to shift the rotated graph in Z direction to match the two
    assert rg.shift_by(dz=2) == rg_from_scratch


def test_block_graph_fix_shadowed_faces() -> None:
    rotated_cnot = cnot().rotate(Direction3D.X, False)
    fixed = rotated_cnot.fix_shadowed_faces()
    assert fixed[Position3D(0, 2, -1)].kind == ZXCube.from_str("ZXX")
    assert fixed[Position3D(1, 1, -2)].kind == ZXCube.from_str("ZXX")


def test_block_graph_to_from_dict() -> None:
    g = memory()
    g_dict = g.to_dict()
    assert g_dict == {
        "cubes": [{"kind": "ZXZ", "label": "", "position": (0, 0, 0), "condition": None}],
        "name": "Logical Z Memory Experiment",
        "pipes": [],
        "ports": {},
    }
    assert g.from_dict(g_dict) == g

    g = cnot()
    g_dict = g.to_dict()
    assert g_dict["name"] == "Logical CNOT"
    assert len(g_dict["cubes"]) == 10
    assert len(g_dict["pipes"]) == 9
    assert len(g_dict["ports"]) == 4
    assert g.from_dict(g_dict) == g


def test_bgraph_write_read() -> None:
    # Small example to test comms between blockgraph and loader/writer
    # The actual read/write operation is tested elsewhere
    block_graph = cnot(Basis.X)

    # Set `delete=False` to be compatible with Windows
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    with tempfile.NamedTemporaryFile(suffix=".bgraph", delete=False) as temp_file:
        _ = block_graph.to_bgraph(temp_file.name)
        block_graph_from_file = BlockGraph.from_bgraph(temp_file.name)
        assert block_graph_from_file == block_graph

    # Manually delete the temporary file
    os.remove(temp_file.name)


def test_block_graph_to_json() -> None:
    g = BlockGraph("Horizontal Hadamard Line")
    n = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "P", "In")
    g.add_pipe(n, n2, "OXZH")
    json_text = g.to_json(indent=None)
    assert (
        json_text
        == """{"name": "Horizontal Hadamard Line", "cubes": [{"position": [0, 0, 0], "kind": "ZXZ", "label": "", "condition": null, "transform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}, {"position": [1, 0, 0], "kind": "PORT", "label": "In", "condition": null, "transform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}], "pipes": [{"u": [0, 0, 0], "v": [1, 0, 0], "kind": "OXZH", "transform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}], "ports": {"In": [1, 0, 0]}}"""  # noqa
    )


def test_block_graph_from_json() -> None:
    g = BlockGraph("Horizontal Hadamard Line")
    n = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_pipe(n, n2, "OXZH")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        g.to_json(temp_file.name)
        read_g = BlockGraph.from_json(temp_file.name, "simple_test")
        assert read_g == g

    os.remove(temp_file.name)


def test_block_graph_relabel_cubes() -> None:
    g = BlockGraph()
    n = g.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_pipe(n, n2, "OXZH")
    n3 = g.add_cube(Position3D(2, 0, 0), "P", "Out")
    g.add_pipe(n2, n3, "OXZH")
    assert g.get_cubes_by_label("In")[0].position == Position3D(0, 0, 0)

    label_mapping: dict[Position3D | str, str] = {
        Position3D(0, 0, 0): "InputPortByPos",
        "Out": "OutputPortByLabel",
    }

    g.relabel_cubes(label_mapping)

    new_labels = {cube.label for cube in g.cubes}
    assert "InputPortByPos" in new_labels
    assert "OutputPortByLabel" in new_labels
    assert "In" not in new_labels
    assert "Out" not in new_labels
    assert g[Position3D(0, 0, 0)].is_port
    assert g[Position3D(2, 0, 0)].is_port
    assert len(g.get_cubes_by_label("In")) == 0


@pytest.mark.parametrize("kind", [LeafCubeKind.PORT, "PORT", "P", " port "])
@pytest.mark.parametrize("by_position", [False, True])
def test_fill_port_rejects_port_without_changing_graph(kind, by_position: bool) -> None:
    graph = BlockGraph()
    body, output = Position3D(0, 0, 0), Position3D(0, 0, 1)
    graph.add_cube(body, "ZXZ")
    graph.add_cube(output, "PORT", label="out")
    graph.add_pipe(body, output)
    before = graph.to_dict()

    with pytest.raises(TQECError, match="Cannot fill a port with PORT"):
        graph.fill_port(output if by_position else "out", kind)

    assert graph.to_dict() == before
    assert graph.num_ports == 1
    assert graph.ordered_ports == ["out"]
    graph.validate()

    graph.fill_port("out", ZXCube.ZXZ)
    assert graph[output].kind is ZXCube.ZXZ
    assert graph.num_ports == 0
    assert graph.ordered_ports == []
    graph.validate()


@pytest.mark.parametrize("failure", ["unknown", "port", "missing_condition"])
def test_fill_ports_failure_is_atomic(failure: str) -> None:
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "P", "in")
    second = graph.add_cube(Position3D(1, 0, 0), "P", "out")
    graph.add_pipe(first, second, "OZX")
    before = graph.to_dict()
    ports_before = graph.ports.copy()
    fill: dict[str, CubeKind] = {"in": ZXCube.XZX}
    if failure == "unknown":
        fill["missing"] = ZXCube.XZX
    elif failure == "port":
        fill["out"] = LeafCubeKind.PORT
    else:
        fill["out"] = ConditionalCubeKind((ZXCube.ZXZ, ZXCube.ZXX))

    with pytest.raises(TQECError):
        graph.fill_ports(fill)

    assert graph.to_dict() == before
    assert graph.ports == ports_before
    graph.validate()


@pytest.mark.parametrize("batch", [False, True])
def test_fill_ports_updates_pipe_endpoints_and_preserves_label_policy(batch: bool) -> None:
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "P", "in")
    second = graph.add_cube(Position3D(1, 0, 0), "P", "out")
    graph.add_pipe(first, second, "OZX")
    if batch:
        graph.fill_ports(ZXCube.XZX)
    else:
        graph.fill_port("in", ZXCube.XZX)
        graph.fill_port(second, ZXCube.XZX)

    assert graph[first].label == ("" if batch else "in")
    assert graph[second].label == ("" if batch else "out")
    assert graph.num_ports == 0
    assert graph.ports == {}
    assert graph.num_pipes == 1
    pipe = graph.pipes[0]
    assert pipe.u is graph[pipe.u.position]
    assert pipe.v is graph[pipe.v.position]
    assert pipe.kind == PipeKind.from_str("OZX")
    graph.validate()


@pytest.mark.parametrize("corruption", ["missing", "extra", "wrong_position"])
def test_validate_rejects_inconsistent_port_index(corruption: str) -> None:
    graph = BlockGraph()
    body = graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    output = graph.add_cube(Position3D(0, 0, 1), "P", "out")
    graph.add_pipe(body, output)
    graph.validate()
    if corruption == "missing":
        graph._ports.clear()
    elif corruption == "extra":
        graph._ports["extra"] = body
    else:
        graph._ports["out"] = body

    with pytest.raises(TQECError, match="Port index does not match"):
        graph.validate()


def test_validate_rejects_duplicate_port_labels() -> None:
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "P", "in")
    second = graph.add_cube(Position3D(1, 0, 0), "P", "out")
    graph.add_pipe(first, second, "OZX")
    graph._graph.nodes[second][graph._NODE_DATA_KEY] = Cube(second, LeafCubeKind.PORT, "in")
    with pytest.raises(TQECError, match="Duplicate port label"):
        graph.validate()


def test_block_graph_add_pipes_automatically() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXX")
    # Not adjacent to anything: sits diagonally from every other cube.
    g.add_cube(Position3D(5, 5, 5), "ZXZ")

    g.add_pipes_automatically()

    assert g.num_pipes == 2
    assert g.has_pipe_between(Position3D(0, 0, 0), Position3D(1, 0, 0))
    assert g.has_pipe_between(Position3D(0, 0, 0), Position3D(0, 0, 1))


def test_block_graph_add_pipes_automatically_preserves_existing() -> None:
    g = BlockGraph()
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))

    g.add_pipes_automatically()

    assert g.num_pipes == 1


def test_component_bounds_empty_graph() -> None:
    """Empty graph returns empty component list."""
    g = BlockGraph("empty")
    bounds = g.component_bounds()
    assert bounds == []


def test_component_bounds_single_component() -> None:
    """Single component gives correct inclusive min/max."""
    g = BlockGraph("single")
    g.add_cube(Position3D(1, 2, 3), "ZXZ")
    g.add_cube(Position3D(1, 2, 4), "ZXZ")  # neighbor in z direction
    g.add_cube(Position3D(2, 2, 4), "ZXZ")  # neighbor in x direction
    g.add_pipe(Position3D(1, 2, 3), Position3D(1, 2, 4))
    g.add_pipe(Position3D(1, 2, 4), Position3D(2, 2, 4))

    bounds = g.component_bounds()

    assert len(bounds) == 1
    assert bounds[0].minimum == Position3D(1, 2, 3)
    assert bounds[0].maximum == Position3D(2, 2, 4)
    assert bounds[0].nodes == frozenset(
        [Position3D(1, 2, 3), Position3D(1, 2, 4), Position3D(2, 2, 4)]
    )


def test_component_bounds_two_components_sorted_by_z() -> None:
    """Two disconnected components sorted by (z, y, x), with z deciding order."""
    g = BlockGraph("two_comps")
    # First component: z=1
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    # Second component: z=0 (should come first after sorting)
    g.add_cube(Position3D(5, 5, 0), "ZXZ")

    bounds = g.component_bounds()

    assert len(bounds) == 2
    # z=0 component comes first
    assert bounds[0].minimum == Position3D(5, 5, 0)
    assert bounds[0].maximum == Position3D(5, 5, 0)
    # z=1 component comes second
    assert bounds[1].minimum == Position3D(0, 0, 1)
    assert bounds[1].maximum == Position3D(1, 0, 1)


def test_component_bounds_multiple_components_sorted_by_yx() -> None:
    """Components at one z are sorted by y, then x."""
    g = BlockGraph("multiple")
    # Component at (2, 1, 0)
    g.add_cube(Position3D(2, 1, 0), "ZXZ")
    # Component at (1, 2, 0) - same z, but y < 1
    g.add_cube(Position3D(1, 2, 0), "ZXZ")
    # Component at (0, 0, 0) - smallest in x and y
    g.add_cube(Position3D(0, 0, 0), "ZXZ")

    bounds = g.component_bounds()

    assert len(bounds) == 3
    # Sorted by (z, y, x)
    assert bounds[0].minimum == Position3D(0, 0, 0)
    assert bounds[1].minimum == Position3D(2, 1, 0)
    assert bounds[2].minimum == Position3D(1, 2, 0)


def test_component_bounds_sorted_by_bounding_box_minimum() -> None:
    """Order uses the box minimum (min z, min y, min x), not the smallest node."""
    g = BlockGraph("box_minimum")
    # Smallest node (z, y, x) = (0, 1, 5), box minimum (0, 0, 5).
    g.add_cube(Position3D(5, 1, 0), "XZZ")
    g.add_cube(Position3D(5, 1, 1), "XZZ")
    g.add_cube(Position3D(5, 0, 1), "XZZ")
    g.add_pipe(Position3D(5, 1, 0), Position3D(5, 1, 1))
    g.add_pipe(Position3D(5, 1, 1), Position3D(5, 0, 1))
    # Box minimum (0, 0, 9), between the two keys of the first component.
    g.add_cube(Position3D(9, 0, 0), "ZXZ")

    bounds = g.component_bounds()

    assert [b.minimum for b in bounds] == [Position3D(5, 0, 0), Position3D(9, 0, 0)]


def test_component_bounds_overlaps_touching_boxes() -> None:
    """overlaps() returns True for touching or overlapping boxes."""
    b1 = ComponentBounds(
        nodes=frozenset([Position3D(0, 0, 0)]),
        minimum=Position3D(0, 0, 0),
        maximum=Position3D(2, 2, 2),
    )
    b2 = ComponentBounds(
        nodes=frozenset([Position3D(2, 2, 2)]),
        minimum=Position3D(2, 2, 2),
        maximum=Position3D(4, 4, 4),
    )
    assert b1.overlaps(b2), "Expected touching boxes to overlap"


def test_component_bounds_overlaps_separated_boxes() -> None:
    """overlaps() returns False for separated boxes."""
    b1 = ComponentBounds(
        nodes=frozenset([Position3D(0, 0, 0)]),
        minimum=Position3D(0, 0, 0),
        maximum=Position3D(1, 1, 1),
    )
    b2 = ComponentBounds(
        nodes=frozenset([Position3D(3, 3, 3)]),
        minimum=Position3D(3, 3, 3),
        maximum=Position3D(4, 4, 4),
    )
    assert not b1.overlaps(b2), "Expected separated boxes not to overlap"


def test_component_bounds_overlaps_separated_in_z_only() -> None:
    """overlaps() returns False when boxes are separated in z only."""
    b1 = ComponentBounds(
        nodes=frozenset([Position3D(0, 0, 0)]),
        minimum=Position3D(0, 0, 0),
        maximum=Position3D(2, 2, 1),
    )
    b2 = ComponentBounds(
        nodes=frozenset([Position3D(0, 0, 3)]),
        minimum=Position3D(0, 0, 3),
        maximum=Position3D(2, 2, 4),
    )
    # Same x and y ranges but separated in z
    assert not b1.overlaps(b2), "Expected boxes separated in z only not to overlap"


def test_component_bounds_frozen() -> None:
    """ComponentBounds is frozen; assigning to attributes raises FrozenInstanceError."""
    bounds = ComponentBounds(
        nodes=frozenset([Position3D(0, 0, 0)]),
        minimum=Position3D(0, 0, 0),
        maximum=Position3D(1, 1, 1),
    )
    with pytest.raises(FrozenInstanceError):
        bounds.minimum = Position3D(2, 2, 2)  # type: ignore
    with pytest.raises(FrozenInstanceError):
        bounds.maximum = Position3D(3, 3, 3)  # type: ignore
    with pytest.raises(FrozenInstanceError):
        bounds.nodes = frozenset()  # type: ignore
