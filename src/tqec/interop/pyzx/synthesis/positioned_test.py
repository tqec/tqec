from fractions import Fraction

from pyzx import VertexType

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx._testing import make_positioned_zx_graph
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis
from tqec.utils.position import Position3D


def test_positioned_synthesis_single_zx_edge() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.X],
        positions=[
            Position3D(0, 0, 0),
            Position3D(1, 0, 0),
        ],
        edges=[(0, 1)],
        hadamard_edges=[False],
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_cube(Position3D(0, 0, 0), "XXZ")
    expected_block.add_cube(Position3D(1, 0, 0), "ZXZ")
    expected_block.add_pipe(
        Position3D(0, 0, 0),
        Position3D(1, 0, 0),
    )
    assert block == expected_block

    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.Z],
        positions=[
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        ],
        edges=[(0, 1)],
        hadamard_edges=[False],
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_cube(Position3D(0, 0, 0), "XZX")
    expected_block.add_cube(Position3D(0, 0, 1), "XZX")
    expected_block.add_pipe(
        Position3D(0, 0, 0),
        Position3D(0, 0, 1),
    )
    assert block == expected_block


def test_positioned_synthesis_single_y_p_edge() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.BOUNDARY],
        positions=[
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
        ],
        phases={0: Fraction(1, 2)},
        edges=[(0, 1)],
        hadamard_edges=[False],
        outputs=(1,),
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_cube(Position3D(0, 0, 0), "Y")
    expected_block.add_cube(Position3D(0, 0, 1), "P", "OUT_0")
    expected_block.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1), "XZO")
    print(block.ports)
    assert block == expected_block


def test_positioned_synthesis_L_shape() -> None:
    g = make_positioned_zx_graph(
        vertex_types=[VertexType.Z, VertexType.BOUNDARY, VertexType.BOUNDARY],
        positions=[
            Position3D(0, 0, 0),
            Position3D(0, 0, 1),
            Position3D(1, 0, 0),
        ],
        edges=[(0, 1), (0, 2)],
        hadamard_edges=[False, False],
        inputs=(1,),
        outputs=(2,),
    )
    block = positioned_block_synthesis(g)
    expected_block = BlockGraph()
    expected_block.add_cube(Position3D(0, 0, 0), "XZX")
    expected_block.add_cube(Position3D(0, 0, 1), "P", "IN_0")
    expected_block.add_cube(Position3D(1, 0, 0), "P", "OUT_0")
    expected_block.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    expected_block.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
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
    expected_block.add_cube(Position3D(0, 0, 0), "XXZ")
    for port, label in zip(ports, ["IN_0", "OUT_0", "OUT_1", "OUT_2"]):
        expected_block.add_cube(port, "P", label)
        expected_block.add_pipe(Position3D(0, 0, 0), port)
    assert block == expected_block
