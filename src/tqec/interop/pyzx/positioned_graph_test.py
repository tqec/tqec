from fractions import Fraction
from typing import Iterable
import pytest

from pyzx.graph.graph_s import GraphS
from pyzx import VertexType, EdgeType

from tqec.utils.exceptions import TQECException
from tqec.interop.pyzx.positioned_graph import PositionedZX
from tqec.utils.position import Position3D


def _check_zx_graph_with_3D_positions(
    vertex_types: list[VertexType],
    positions: list[Position3D],
    edges: Iterable[tuple[int, int]] = (),
    hadamard_edges: Iterable[bool] = (),
    phases: dict[int, Fraction] = {},
    inputs: tuple[int, ...] = (),
    outputs: tuple[int, ...] = (),
) -> None:
    g = GraphS()
    for i, vt in enumerate(vertex_types):
        g.add_vertex(vt)
        if i in phases:
            g.set_phase(i, phases[i])
    for (s, t), hadamard in zip(edges, hadamard_edges):
        g.add_edge((s, t), EdgeType.HADAMARD if hadamard else EdgeType.SIMPLE)
    g.set_inputs(inputs)
    g.set_outputs(outputs)
    PositionedZX.check_preconditions(g, {i: p for i, p in enumerate(positions)})


def test_positions_not_specified() -> None:
    g = GraphS()
    g.add_vertex(VertexType.Z)
    with pytest.raises(
        TQECException,
        match=r".* do not match.*",
    ):
        PositionedZX(g, {})


def test_positions_not_neighbors() -> None:
    with pytest.raises(TQECException, match=r".* must be neighbors.*"):
        _check_zx_graph_with_3D_positions(
            vertex_types=[VertexType.Z, VertexType.Z],
            positions=[Position3D(0, 0, 0), Position3D(2, 0, 0)],
            edges=[(0, 1)],
            hadamard_edges=[False],
        )


def test_unsupported_vertex_type() -> None:
    with pytest.raises(TQECException, match=r"Unsupported vertex type and phase.*"):
        _check_zx_graph_with_3D_positions(
            vertex_types=[VertexType.Z],
            positions=[Position3D(0, 0, 0)],
            phases={0: Fraction(1, 3)},
        )


def test_boundary_not_dangle() -> None:
    with pytest.raises(TQECException, match=r".* must be dangling.*"):
        _check_zx_graph_with_3D_positions(
            vertex_types=[VertexType.BOUNDARY, VertexType.Z, VertexType.X],
            positions=[Position3D(0, 0, 0), Position3D(1, 0, 0), Position3D(0, 1, 0)],
            edges=[(0, 1), (0, 2)],
            hadamard_edges=[False, False],
            inputs=(0,),
        )


def test_y_connect_in_space() -> None:
    with pytest.raises(TQECException, match=r".* must connect to the time direction.*"):
        _check_zx_graph_with_3D_positions(
            vertex_types=[VertexType.Z, VertexType.Z],
            positions=[Position3D(0, 0, 0), Position3D(1, 0, 0)],
            phases={1: Fraction(1, 2)},
            edges=[(0, 1)],
            hadamard_edges=[False],
        )


def test_3d_corner() -> None:
    with pytest.raises(TQECException, match=r".* has a 3D corner.*"):
        _check_zx_graph_with_3D_positions(
            vertex_types=[VertexType.Z] * 4,
            positions=[
                Position3D(0, 0, 0),
                Position3D(1, 0, 0),
                Position3D(0, 1, 0),
                Position3D(0, 0, 1),
            ],
            edges=[(0, 1), (0, 2), (0, 3)],
            hadamard_edges=[False] * 3,
        )
