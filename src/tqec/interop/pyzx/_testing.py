from collections.abc import Iterable
from fractions import Fraction

from pyzx import EdgeType, VertexType
from pyzx.graph.graph_s import GraphS

from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.position import Position3D


def make_positioned_zx_graph(
    vertex_types: list[VertexType],
    positions: list[Position3D],
    edges: Iterable[tuple[int, int]] = (),
    hadamard_edges: Iterable[bool] = (),
    phases: dict[int, Fraction] = {},
    inputs: tuple[int, ...] = (),
    outputs: tuple[int, ...] = (),
) -> PositionedZX:
    g = GraphS()
    for i, vt in enumerate(vertex_types):
        g.add_vertex(vt)
        if i in phases:
            g.set_phase(i, phases[i])
    for (s, t), hadamard in zip(edges, hadamard_edges):
        g.add_edge((s, t), EdgeType.HADAMARD if hadamard else EdgeType.SIMPLE)
    g.set_inputs(inputs)
    g.set_outputs(outputs)
    return PositionedZX(g, {i: p for i, p in enumerate(positions)})
