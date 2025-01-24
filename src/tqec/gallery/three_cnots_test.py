from typing import Literal

from tqec.computation.zx_graph import ZXKind
from tqec.gallery.three_cnots import three_cnots_zx_graph


def test_three_cnots_zx_graph_OPEN() -> None:
    g = three_cnots_zx_graph("OPEN")
    assert g.num_ports == 6
    assert g.num_nodes == 12
    assert g.num_edges == 12
    assert len(g.leaf_nodes) == 6
    assert len([n for n in g.nodes if n.kind == ZXKind.Z]) == 4
    assert len([n for n in g.nodes if n.kind == ZXKind.X]) == 2
    assert {*g.ports.keys()} == {
        "In_a",
        "Out_a",
        "In_b",
        "Out_b",
        "In_c",
        "Out_c",
    }


def test_three_cnots_zx_graph_filled() -> None:
    port_type: Literal["X", "Z"]
    for port_type in ("X", "Z"):
        g = three_cnots_zx_graph(port_type)
        assert g.num_ports == 0
        assert g.num_nodes == 12
        assert g.num_edges == 12
        assert len(g.leaf_nodes) == 6
        num_x_nodes = len([n for n in g.nodes if n.kind == ZXKind.X])
        num_z_nodes = len([n for n in g.nodes if n.kind == ZXKind.Z])
        if port_type == "X":
            assert num_x_nodes == 8
            assert num_z_nodes == 4
        else:
            assert num_x_nodes == 2
            assert num_z_nodes == 10


def test_three_cnots_correlation_surface() -> None:
    g = three_cnots_zx_graph("X")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 7

    g = three_cnots_zx_graph("X")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 7

    g = three_cnots_zx_graph("OPEN")
    correlation_surfaces = g.find_correlation_surfaces()
    all_external_stabilizers = [cs.external_stabilizer for cs in correlation_surfaces]
    assert all(
        [
            s in all_external_stabilizers
            for s in [
                {
                    "In_a": "X",
                    "Out_a": "X",
                    "In_b": "X",
                    "Out_b": "I",
                    "In_c": "X",
                    "Out_c": "I",
                },
                {
                    "In_a": "I",
                    "Out_a": "I",
                    "In_b": "X",
                    "Out_b": "X",
                    "In_c": "X",
                    "Out_c": "I",
                },
                {
                    "In_a": "I",
                    "Out_a": "I",
                    "In_b": "I",
                    "Out_b": "I",
                    "In_c": "X",
                    "Out_c": "X",
                },
                {
                    "In_a": "Z",
                    "Out_a": "Z",
                    "In_b": "I",
                    "Out_b": "I",
                    "In_c": "I",
                    "Out_c": "I",
                },
                {
                    "In_a": "Z",
                    "Out_a": "I",
                    "In_b": "Z",
                    "Out_b": "Z",
                    "In_c": "I",
                    "Out_c": "I",
                },
                {
                    "In_a": "I",
                    "Out_a": "I",
                    "In_b": "Z",
                    "Out_b": "I",
                    "In_c": "Z",
                    "Out_c": "Z",
                },
            ]
        ]
    )
