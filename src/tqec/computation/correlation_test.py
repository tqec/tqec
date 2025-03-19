from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.utils.enums import Basis


def test_zx_node() -> None:
    n1 = ZXNode(0, Basis.Z)
    n2 = ZXNode(1, Basis.X)
    assert n1 < n2


def test_zx_edge() -> None:
    e1 = ZXEdge(
        ZXNode(1, Basis.Z),
        ZXNode(0, Basis.Z),
    )
    assert e1.u < e1.v
    assert not e1.is_self_loop()
    assert not e1.has_hadamard

    e2 = ZXEdge(
        ZXNode(1, Basis.Z),
        ZXNode(2, Basis.X),
    )
    assert e2.has_hadamard

    e3 = ZXEdge(
        ZXNode(0, Basis.Z),
        ZXNode(0, Basis.Z),
    )
    assert e3.is_self_loop()


def test_single_node_correlation_surface() -> None:
    surface = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(0, Basis.Z),
                    ZXNode(0, Basis.Z),
                ),
            ]
        )
    )
    assert surface.bases_at(0) == {Basis.Z}
    assert surface.is_single_node
    assert surface.span_vertices() == {0}
    assert surface.external_stabilizer([0]) == "Z"
    assert surface.area() == 1


def test_y_edge_correlation_surface() -> None:
    surface = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(0, Basis.Z),
                    ZXNode(1, Basis.Z),
                ),
                ZXEdge(
                    ZXNode(0, Basis.X),
                    ZXNode(1, Basis.X),
                ),
            ]
        )
    )
    assert surface.bases_at(0) == {Basis.Z, Basis.X}
    assert surface.bases_at(1) == {Basis.Z, Basis.X}
    assert not surface.is_single_node
    assert surface.span_vertices() == {0, 1}
    assert surface.external_stabilizer([0, 1]) == "YY"
    assert surface.area() == 4


def test_correlation_surface_xor() -> None:
    s1 = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(0, Basis.Z),
                    ZXNode(1, Basis.Z),
                ),
                ZXEdge(
                    ZXNode(0, Basis.X),
                    ZXNode(1, Basis.X),
                ),
            ]
        )
    )
    s2 = CorrelationSurface(
        span=frozenset(
            [
                ZXEdge(
                    ZXNode(0, Basis.X),
                    ZXNode(1, Basis.X),
                ),
            ]
        )
    )
    s12 = s1 ^ s2
    assert s12.span == frozenset(
        [
            ZXEdge(
                ZXNode(0, Basis.Z),
                ZXNode(1, Basis.Z),
            ),
        ]
    )
