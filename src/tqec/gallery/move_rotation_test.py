from typing import Literal

from tqec.computation.zx_graph import ZXKind
from tqec.gallery.move_rotation import move_rotation_zx_graph


def test_move_rotation_zx_graph_open() -> None:
    g = move_rotation_zx_graph("OPEN")
    assert g.num_ports == 2
    assert g.num_nodes == 5
    assert g.num_edges == 4
    assert len(g.leaf_nodes) == 2
    assert len([n for n in g.nodes if n.kind == ZXKind.Z]) == 2
    assert len([n for n in g.nodes if n.kind == ZXKind.X]) == 1
    assert {*g.ports.keys()} == {
        "In",
        "Out",
    }


def test_move_rotation_zx_graph_filled() -> None:
    port_type: Literal["X", "Z"]
    for port_type in ("X", "Z"):
        g = move_rotation_zx_graph(port_type)
        assert g.num_ports == 0
        assert g.num_nodes == 5
        assert g.num_edges == 4
        assert len(g.leaf_nodes) == 2
        num_x_nodes = len([n for n in g.nodes if n.kind == ZXKind.X])
        num_z_nodes = len([n for n in g.nodes if n.kind == ZXKind.Z])
        if port_type == "X":
            assert num_x_nodes == 3
            assert num_z_nodes == 2
        else:
            assert num_x_nodes == 1
            assert num_z_nodes == 4


def test_move_rotation_correlation_surface() -> None:
    g = move_rotation_zx_graph("X")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1

    g = move_rotation_zx_graph("Z")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1

    g = move_rotation_zx_graph("OPEN")
    correlation_surfaces = g.find_correlation_surfaces()
    all_external_stabilizers = [cs.external_stabilizer for cs in correlation_surfaces]
    assert all(
        [
            s in all_external_stabilizers
            for s in [
                {
                    "In": "X",
                    "Out": "X",
                },
                {
                    "In": "Z",
                    "Out": "Z",
                },
            ]
        ]
    )
