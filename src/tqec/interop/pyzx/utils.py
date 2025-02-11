"""Utility functions for PyZX interop."""

from fractions import Fraction

import pyzx as zx
from pyzx.graph.graph_s import GraphS
from pyzx.utils import FractionLike, VertexType, vertex_is_zx

from tqec.computation.cube import CubeKind, Port, ZXCube
from tqec.utils.enums import Basis


def is_zx_no_phase(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a Z/X spider with phase 0."""
    return vertex_is_zx(g.type(v)) and g.phase(v) == 0


def is_z_no_phase(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a Z spider with phase 0."""
    return g.type(v) is VertexType.Z and g.phase(v) == 0


def is_x_no_phase(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a X spider with phase 0."""
    return g.type(v) is VertexType.X and g.phase(v) == 0


def is_boundary(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a boundary type spider."""
    return g.type(v) is zx.VertexType.BOUNDARY


def is_s(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a S node."""
    return g.type(v) is zx.VertexType.Z and g.phase(v) == Fraction(1, 2)


def is_hardmard(g: GraphS, edge: tuple[int, int]) -> bool:
    """Check if an edge in a PyZX graph is a Hadamard edge."""
    return g.edge_type(edge) is zx.EdgeType.HADAMARD


def cube_kind_to_zx(kind: CubeKind) -> tuple[zx.VertexType, FractionLike]:
    """Convert the cube kind to the corresponding PyZX vertex type and phase.

    The conversion is as follows:

    - Port -> BOUNDARY spider with phase 0.
    - YCube -> Z spider with phase 1/2.
    - ZXCube -> Z spider with phase 0 if it has only one Z basis boundary,
        otherwise X spider with phase 0.

    Args:
        kind: The cube kind to be converted.

    Returns:
        A tuple of vertex type and spider phase.
    """
    if isinstance(kind, ZXCube):
        if sum(basis == Basis.Z for basis in kind.as_tuple()) == 1:
            return zx.VertexType.Z, 0
        return zx.VertexType.X, 0
    if isinstance(kind, Port):
        return zx.VertexType.BOUNDARY, 0
    else:  # isinstance(kind, YCube)
        return zx.VertexType.Z, Fraction(1, 2)
