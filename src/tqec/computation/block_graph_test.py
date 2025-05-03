import os
import tempfile
import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.gallery import cz, memory, cnot
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
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

    with pytest.raises(TQECException, match="Cube already exists at position .*"):
        g.add_cube(Position3D(0, 0, 0), "XZX")

    v = g.add_cube(Position3D(1, 0, 0), "PORT", "P")
    assert g.num_cubes == 2
    assert g.num_ports == 1
    assert g.spacetime_volume == 1
    assert g[v].is_port

    with pytest.raises(TQECException, match=".* port with the same label .*"):
        g.add_cube(Position3D(10, 0, 0), "P", "P")


def test_block_graph_add_pipe() -> None:
    g = BlockGraph()
    with pytest.raises(TQECException, match="No cube at position .*"):
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

    with pytest.raises(TQECException, match=".* already a pipe between .*"):
        g.add_pipe(
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        )

    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    with pytest.raises(TQECException, match=r"No pipe between .*"):
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
    with pytest.raises(TQECException, match="has non-timelike pipes connected"):
        g.validate()

    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 1), "Y")
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
        g.validate()
    n2 = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n3 = g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    with pytest.raises(TQECException, match="does not have exactly one pipe connected"):
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

    with pytest.raises(TQECException):
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
    with pytest.raises(TQECException):
        g.rotate(Direction3D.X)
    rg = g.rotate(Direction3D.Z)
    assert Position3D(-1, 0, 0) in rg
    assert str(rg.cubes[0].kind) == "Y"


@pytest.mark.parametrize("obs_basis", [Basis.Z, Basis.X, None])
def test_cnot_graph_rotation(obs_basis: Basis | None) -> None:
    from tqec.interop.collada.read_write_test import rotated_cnot
    from tqec.gallery.cnot import cnot

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
        "cubes": [{"kind": "ZXZ", "label": "", "position": (0, 0, 0)}],
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


def test_block_graph_to_from_json() -> None:
    g = BlockGraph("Horizontal Hadamard Line")
    n = g.add_cube(Position3D(0, 0, 0), "ZXZ")
    n2 = g.add_cube(Position3D(1, 0, 0), "P", "In")
    g.add_pipe(n, n2, "OXZH")
    json_text = g.to_json(indent=None)
    assert (
        json_text
        == """{"name": "Horizontal Hadamard Line", "cubes": [{"position": [0, 0, 0], "kind": "ZXZ", "label": ""}, {"position": [1, 0, 0], "kind": "PORT", "label": "In"}], "pipes": [{"u": [0, 0, 0], "v": [1, 0, 0], "kind": "OXZH"}], "ports": {"In": [1, 0, 0]}}"""
    )
    assert g.from_json(json_text=json_text) == g

    g = cz()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        g.to_json(temp_file.name)
        read_g = BlockGraph.from_json(temp_file.name)
        assert read_g == g
    os.remove(temp_file.name)


def test_block_graph_relabel_cubes() -> None:
    g = BlockGraph()
    n = g.add_cube(Position3D(0, 0, 0), "P", "In")
    n2 = g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_pipe(n, n2, "OXZH")
    n3 = g.add_cube(Position3D(2, 0, 0), "P", "Out")
    g.add_pipe(n2, n3, "OXZH")

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
