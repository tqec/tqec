from fractions import Fraction

from pyzx import VertexType

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, YCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.interop.pyzx._testing import make_positioned_zx_graph
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis
from tqec.utils.position import Position3D


def test_positioned_synthesis_single_zx_edge() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.X],
        positions=[Position3D(0, 0, 0), Position3D(1, 0, 0)],
        edges=[(0, 1)],
        hadamard_edges=[False],
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
    )
    assert block == expected_block

    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.Z],
        positions=[Position3D(0, 0, 0), Position3D(0, 0, 1)],
        edges=[(0, 1)],
        hadamard_edges=[False],
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("XZX")),
    )
    assert block == expected_block


def test_positioned_synthesis_single_y_p_edge() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.BOUNDARY],
        positions=[Position3D(0, 0, 0), Position3D(0, 0, 1)],
        phases={0: Fraction(1, 2)},
        edges=[(0, 1)],
        hadamard_edges=[False],
        outputs=(1,),
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), YCube()),
        Cube(Position3D(0, 0, 1), Port(), "OUT_0"),
        PipeKind.from_str("XZO"),
    )
    assert block == expected_block


def test_positioned_synthesis_L_shape() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.BOUNDARY, VertexType.BOUNDARY],
        positions=[Position3D(0, 0, 0), Position3D(0, 0, 1), Position3D(1, 0, 0)],
        edges=[(0, 1), (0, 2)],
        hadamard_edges=[False, False],
        inputs=(1,),
        outputs=(2,),
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(0, 0, 1), Port(), "IN_0"),
    )
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XZX")),
        Cube(Position3D(1, 0, 0), Port(), "OUT_0"),
    )
    assert block == expected_block


def test_positioned_synthesis_X_shape() -> None:
    ports = [
        Position3D(1, 0, 0),
        Position3D(0, 1, 0),
        Position3D(-1, 0, 0),
        Position3D(0, -1, 0),
    ]
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z] + [VertexType.BOUNDARY] * 4,
        positions=[Position3D(0, 0, 0)] + ports,
        edges=[(0, 1), (0, 2), (0, 3), (0, 4)],
        hadamard_edges=[False] * 4,
        inputs=(1,),
        outputs=(2, 3, 4),
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(ports[0], Port(), "IN_0"),
    )
    for i, port in enumerate(ports[1:]):
        expected_block.add_edge(
            Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
            Cube(port, Port(), f"OUT_{i}"),
        )
    assert block == expected_block
