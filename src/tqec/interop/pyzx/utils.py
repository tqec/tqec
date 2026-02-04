"""Utility functions for PyZX interop."""

from fractions import Fraction

from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, FractionLike, VertexType, vertex_is_zx

from tqec.computation.cube import ConditionalLeafCubeKind, CubeKind, LeafCubeKind, ZXCube
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError


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
    return g.type(v) is VertexType.BOUNDARY


def is_s(g: GraphS, v: int) -> bool:
    """Check if a vertex in a PyZX graph is a S node."""
    return g.type(v) is VertexType.Z and g.phase(v) == Fraction(1, 2)


def is_hadamard(g: GraphS, edge: tuple[int, int]) -> bool:
    """Check if an edge in a PyZX graph is a Hadamard edge."""
    return g.edge_type(edge) is EdgeType.HADAMARD


def cube_kind_to_zx(kind: CubeKind) -> tuple[VertexType, FractionLike]:
    """Convert the cube kind to the corresponding PyZX vertex type and phase.

    The conversion is as follows:

    - Port -> BOUNDARY spider with phase 0.
    - YHalfCube -> Z spider with phase 1/2.
    - ZXCube -> Z spider with phase 0 if it has only one Z basis boundary,
        otherwise X spider with phase 0.

    Args:
        kind: The cube kind to be converted.

    Returns:
        A tuple of vertex type and spider phase.

    """
    if isinstance(kind, ZXCube):
        match kind.normal_basis:
            case Basis.Z:
                return VertexType.Z, 0
            case Basis.X:
                return VertexType.X, 0
    if kind is LeafCubeKind.PORT:
        return VertexType.BOUNDARY, 0
    if kind is LeafCubeKind.Y_HALF_CUBE:
        return VertexType.Z, Fraction(1, 2)
    if isinstance(kind, ConditionalLeafCubeKind):
        raise NotImplementedError(
            "Conversion of conditional cube to PyZX vertex type and phase is not implemented."
        )
    raise TQECError(f"Cannot convert cube kind {kind} to PyZX vertex type and phase.")


def zx_to_pauli(g: GraphS, v: int) -> Pauli:
    """Convert a PyZX vertex to the corresponding Pauli operator.

    Args:
        g: The PyZX graph.
        v: The vertex id.

    Raises:
        ValueError: If the vertex is not a Clifford or a boundary.

    Returns:
        The corresponding Pauli operator.

    """
    return vertex_type_to_pauli(g.type(v), g.phase(v))


def vertex_type_to_pauli(vertex_type: VertexType, phase: FractionLike = 0) -> Pauli:
    """Convert a PyZX vertex type to the corresponding Pauli operator.

    Args:
        vertex_type: The PyZX vertex type.
        phase: The phase of the vertex. Default is 0.

    Raises:
        TQECError: If the vertex type and phase do not correspond to a Pauli operator.

    Returns:
        The corresponding Pauli operator.

    """
    match vertex_type, phase:
        case VertexType.X, 0:
            return Pauli.X
        case VertexType.Z, 0:
            return Pauli.Z
        case VertexType.Z, Fraction(numerator=1, denominator=2):
            return Pauli.Y
        case VertexType.BOUNDARY, _:
            return Pauli.I
        case _:
            raise TQECError(
                f"Cannot convert vertex type {vertex_type} and phase {phase} to Pauli operator."
            )


def zx_to_basis(g: GraphS, v: int) -> Basis:
    """Convert a PyZX vertex to the corresponding Basis.

    Args:
        g: The PyZX graph.
        v: The vertex id.

    Raises:
        ValueError: If the vertex is not a Clifford or a boundary.

    Returns:
        The corresponding Basis.

    """
    return vertex_type_to_basis(g.type(v), g.phase(v))


def vertex_type_to_basis(vertex_type: VertexType, phase: FractionLike = 0) -> Basis:
    """Convert a PyZX vertex type to the corresponding Basis.

    Args:
        vertex_type: The PyZX vertex type.
        phase: The phase of the vertex. Default is 0.

    Raises:
        TQECError: If the vertex type and phase do not correspond to a Basis.

    Returns:
        The corresponding Basis.

    """
    try:
        return vertex_type_to_pauli(vertex_type, phase).to_basis()
    except TQECError:
        raise TQECError(f"Cannot convert vertex type {vertex_type} and phase {phase} to Basis.")
