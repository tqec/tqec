import pytest

from tqec.computation.zx_graph import ZXKind
from tqec.utils.exceptions import TQECException
from tqec.gallery.logical_cz import logical_cz_zx_graph
from tqec.utils.position import Position3D


def test_logical_cz_zx_graph_open() -> None:
    g = logical_cz_zx_graph(None)
    assert g.num_ports == 4
    assert g.num_nodes == 6
    assert g.num_edges == 5
    assert len(g.leaf_nodes) == 4
    assert len([n for n in g.nodes if n.kind == ZXKind.Z]) == 2
    assert len([n for n in g.nodes if n.kind == ZXKind.X]) == 0
    assert {*g.ports.keys()} == {
        "In_1",
        "Out_1",
        "In_2",
        "Out_2",
    }


def test_logical_cz_resolve_ports() -> None:
    in1, in2, out1, out2 = (
        Position3D(0, 0, 0),
        Position3D(1, -1, 1),
        Position3D(0, 0, 2),
        Position3D(1, 1, 1),
    )
    g = logical_cz_zx_graph("XI -> XZ")
    assert g[in1].kind == ZXKind.Z
    assert g[out1].kind == ZXKind.Z
    assert g[in2].kind == ZXKind.X
    assert g[out2].kind == ZXKind.X

    g = logical_cz_zx_graph(["XI -> XZ", "IZ -> IZ"])
    assert g[in1].kind == ZXKind.Z
    assert g[out1].kind == ZXKind.Z
    assert g[in2].kind == ZXKind.X
    assert g[out2].kind == ZXKind.X

    g = logical_cz_zx_graph(["ZX -> IX"])
    assert g[in1].kind == ZXKind.X
    assert g[out1].kind == ZXKind.X
    assert g[in2].kind == ZXKind.Z
    assert g[out2].kind == ZXKind.Z

    g = logical_cz_zx_graph(["ZZ -> ZZ"])
    assert g[in1].kind == ZXKind.X
    assert g[out1].kind == ZXKind.X
    assert g[in2].kind == ZXKind.X
    assert g[out2].kind == ZXKind.X

    with pytest.raises(
        TQECException,
        match="Y basis initialization/measurements are not supported yet.",
    ):
        logical_cz_zx_graph("YI -> XZ")

    with pytest.raises(
        TQECException, match="X_ -> XX is not a valid flow for the CZ gate."
    ):
        logical_cz_zx_graph("XI -> XX")

    with pytest.raises(
        TQECException, match="Port 0 fails to support both X and Z observable."
    ):
        logical_cz_zx_graph(["XI -> XZ", "ZI -> ZI"])


def test_logical_cz_correlation_surface() -> None:
    g = logical_cz_zx_graph("XI -> XZ")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 3

    g = logical_cz_zx_graph(None)
    correlation_surfaces = g.find_correlation_surfaces()
    all_external_stabilizers = [cs.external_stabilizer for cs in correlation_surfaces]
    assert all(
        [
            s in all_external_stabilizers
            for s in [
                {
                    "In_1": "X",
                    "Out_1": "X",
                    "In_2": "I",
                    "Out_2": "Z",
                },
                {
                    "In_1": "I",
                    "Out_1": "Z",
                    "In_2": "X",
                    "Out_2": "X",
                },
                {
                    "In_1": "I",
                    "Out_1": "I",
                    "In_2": "Z",
                    "Out_2": "Z",
                },
                {
                    "In_1": "Z",
                    "Out_1": "Z",
                    "In_2": "I",
                    "Out_2": "I",
                },
            ]
        ]
    )
