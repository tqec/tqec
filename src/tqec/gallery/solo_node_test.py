from tqec.computation.cube import Cube, ZXCube
from tqec.computation.zx_graph import ZXKind
from tqec.gallery.solo_node import solo_node_block_graph, solo_node_zx_graph
from tqec.position import Position3D


def test_solo_node_zx_graph() -> None:
    g = solo_node_zx_graph("Z")
    assert len(g.nodes) == 1
    assert g.nodes[0].kind == ZXKind.Z

    g = solo_node_zx_graph("X")
    assert len(g.nodes) == 1
    assert g.nodes[0].kind == ZXKind.X


def test_solo_node_block_graph() -> None:
    g = solo_node_block_graph("X")
    assert len(g.nodes) == 1
    assert g.nodes[0] == Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXX"))

    g = solo_node_block_graph("Z")
    assert len(g.nodes) == 1
    assert g.nodes[0] == Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))
