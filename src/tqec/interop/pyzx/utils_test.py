from fractions import Fraction
from pyzx.graph.graph_s import GraphS
from pyzx.utils import VertexType
from tqec.computation.cube import Port, YCube, ZXCube
from tqec.interop.pyzx.utils import cube_kind_to_zx, is_boundary, is_zx_no_phase


def test_is_zx_no_phase() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.BOUNDARY)
    v2 = g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    v3 = g.add_vertex(VertexType.X)
    v4 = g.add_vertex(VertexType.Z)
    assert not is_zx_no_phase(g, v1)
    assert not is_zx_no_phase(g, v2)
    assert is_zx_no_phase(g, v3)
    assert is_zx_no_phase(g, v4)


def test_is_boundary() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.BOUNDARY)
    v2 = g.add_vertex(VertexType.Z)
    assert is_boundary(g, v1)
    assert not is_boundary(g, v2)


def test_cube_kind_to_zx() -> None:
    assert cube_kind_to_zx(ZXCube.from_str("ZXZ")) == (VertexType.X, 0)
    assert cube_kind_to_zx(ZXCube.from_str("ZZX")) == (VertexType.X, 0)
    assert cube_kind_to_zx(ZXCube.from_str("XXZ")) == (VertexType.Z, 0)
    assert cube_kind_to_zx(ZXCube.from_str("XZX")) == (VertexType.Z, 0)
    assert cube_kind_to_zx(Port()) == (VertexType.BOUNDARY, 0)
    assert cube_kind_to_zx(YCube()) == (VertexType.Z, Fraction(1, 2))
