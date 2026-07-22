from fractions import Fraction

from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.computation.cube import LeafCubeKind, ZXCube
from tqec.interop.pyzx.utils import (
    cube_kind_to_zx,
    is_boundary,
    is_hadamard,
    is_s,
    is_x_no_phase,
    is_z_no_phase,
    is_zx_no_phase,
    zx_to_basis,
    zx_to_pauli,
)
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError


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


def test_is_z_no_phase() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.Z)
    v2 = g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    v3 = g.add_vertex(VertexType.X)
    v4 = g.add_vertex(VertexType.BOUNDARY)
    assert is_z_no_phase(g, v1)
    assert not is_z_no_phase(g, v2)
    assert not is_z_no_phase(g, v3)
    assert not is_z_no_phase(g, v4)


def test_is_x_no_phase() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.X)
    v2 = g.add_vertex(VertexType.X, phase=Fraction(1, 2))
    v3 = g.add_vertex(VertexType.Z)
    v4 = g.add_vertex(VertexType.BOUNDARY)
    assert is_x_no_phase(g, v1)
    assert not is_x_no_phase(g, v2)
    assert not is_x_no_phase(g, v3)
    assert not is_x_no_phase(g, v4)


def test_is_s() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    v2 = g.add_vertex(VertexType.Z)
    v3 = g.add_vertex(VertexType.X, phase=Fraction(1, 2))
    v4 = g.add_vertex(VertexType.BOUNDARY)
    assert is_s(g, v1)
    assert not is_s(g, v2)
    assert not is_s(g, v3)
    assert not is_s(g, v4)


def test_is_hadamard() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.Z)
    v2 = g.add_vertex(VertexType.X)
    v3 = g.add_vertex(VertexType.X)
    g.add_edge((v1, v2), edgetype=EdgeType.HADAMARD)
    g.add_edge((v2, v3))
    assert is_hadamard(g, (v1, v2))
    assert not is_hadamard(g, (v2, v3))


def test_cube_kind_to_zx() -> None:
    assert cube_kind_to_zx(ZXCube.from_str("ZXZ")) == (VertexType.X, 0)
    assert cube_kind_to_zx(ZXCube.from_str("ZZX")) == (VertexType.X, 0)
    assert cube_kind_to_zx(ZXCube.from_str("XXZ")) == (VertexType.Z, 0)
    assert cube_kind_to_zx(ZXCube.from_str("XZX")) == (VertexType.Z, 0)
    assert cube_kind_to_zx(LeafCubeKind.PORT) == (VertexType.BOUNDARY, 0)
    assert cube_kind_to_zx(LeafCubeKind.Y_HALF_CUBE) == (VertexType.Z, Fraction(1, 2))


def test_zx_to_pauli() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.Z)
    v2 = g.add_vertex(VertexType.X)
    v3 = g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    v4 = g.add_vertex(VertexType.BOUNDARY)
    v5 = g.add_vertex(VertexType.Z, phase=Fraction(1, 4))
    assert zx_to_pauli(g, v1) == Pauli.Z
    assert zx_to_pauli(g, v2) == Pauli.X
    assert zx_to_pauli(g, v3) == Pauli.Y
    assert zx_to_pauli(g, v4) == Pauli.I
    try:
        zx_to_pauli(g, v5)
    except TQECError:
        pass
    else:
        assert False


def test_zx_to_basis() -> None:
    g = GraphS()
    v1 = g.add_vertex(VertexType.Z)
    v2 = g.add_vertex(VertexType.X)
    v3 = g.add_vertex(VertexType.Z, phase=Fraction(1, 2))
    v4 = g.add_vertex(VertexType.BOUNDARY)
    assert zx_to_basis(g, v1) == Basis.Z
    assert zx_to_basis(g, v2) == Basis.X
    for v in [v3, v4]:
        try:
            zx_to_basis(g, v)
        except TQECError:  # noqa: PERF203
            pass
        else:
            assert False
