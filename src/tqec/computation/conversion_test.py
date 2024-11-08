from typing import Literal
import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, YCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.computation.zx_graph import ZXGraph, ZXKind, ZXNode
from tqec.exceptions import TQECException
from tqec.gallery.logical_cnot import logical_cnot_block_graph, logical_cnot_zx_graph
from tqec.gallery.three_cnots import three_cnots_block_graph, three_cnots_zx_graph
from tqec.position import Position3D


def test_conversion_invalid_zx_graph() -> None:
    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.Y),
    )
    with pytest.raises(
        TQECException, match="The Y node must only has Z-direction edge."
    ):
        g.to_block_graph()

    g = ZXGraph()
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, 1, 0), ZXKind.Z),
    )
    g.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    with pytest.raises(TQECException, match="ZX graph has a 3D corner"):
        g.to_block_graph()


def test_conversion_single_zx_edge() -> None:
    zx = ZXGraph()
    zx.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.X),
    )
    block = zx.to_block_graph()
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("OXZ"),
    )
    assert block == expected_block
    assert block.to_zx_graph() == zx

    zx = ZXGraph()
    zx.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, 0, 1), ZXKind.Z),
    )
    block = zx.to_block_graph()
    expected_block = BlockGraph("single edge")
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("XZX")),
        PipeKind.from_str("XZO"),
    )
    assert block == expected_block
    assert block.to_zx_graph() == zx


def test_conversion_single_y_p_edge() -> None:
    zx = ZXGraph()
    zx.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Y),
        ZXNode(Position3D(0, 0, 1), ZXKind.P, "out"),
    )
    block = zx.to_block_graph()
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), YCube()),
        Cube(Position3D(0, 0, 1), Port(), "out"),
        PipeKind.from_str("XZO"),
    )
    assert block == expected_block
    assert block.to_zx_graph() == zx


def test_conversion_L_shape() -> None:
    zx = ZXGraph()
    zx.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(0, 0, 1), ZXKind.P, "p1"),
    )
    zx.add_edge(
        ZXNode(Position3D(0, 0, 0), ZXKind.Z),
        ZXNode(Position3D(1, 0, 0), ZXKind.P, "p2"),
    )
    block = zx.to_block_graph()
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(0, 0, 1), Port(), "p1"),
        PipeKind.from_str("XZO"),
    )
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(1, 0, 0), Port(), "p2"),
        PipeKind.from_str("OZX"),
    )
    assert block == expected_block
    assert block.to_zx_graph() == zx


@pytest.mark.parametrize(
    ("port_kind", "support_observable_basis"),
    zip(("Z", "X", "OPEN"), ("X", "Z", "BOTH")),
)
def test_conversion_logical_cnot(
    port_kind: Literal["Z", "X", "OPEN"],
    support_observable_basis: Literal["Z", "X", "BOTH"],
) -> None:
    block = logical_cnot_block_graph(support_observable_basis)
    assert block.to_zx_graph() == logical_cnot_zx_graph(port_kind)


@pytest.mark.parametrize(
    ("port_kind", "support_observable_basis"),
    zip(("Z", "X", "OPEN"), ("X", "Z", "BOTH")),
)
def test_conversion_three_cnots(
    port_kind: Literal["Z", "X", "OPEN"],
    support_observable_basis: Literal["Z", "X", "BOTH"],
) -> None:
    block = three_cnots_block_graph(support_observable_basis)
    assert block.to_zx_graph() == three_cnots_zx_graph(port_kind)
