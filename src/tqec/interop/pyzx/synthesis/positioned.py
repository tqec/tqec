"""Mapping from a positioned ZX graph to a block graph."""

from typing import cast

import pyzx as zx
from pyzx.utils import vertex_is_zx

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, YHalfCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import is_boundary, is_zx_no_phase
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D


def positioned_block_synthesis(g: PositionedZX) -> BlockGraph:
    """Convert a positioned ZX graph to a :py:class:`~tqec.computation.block_graph.BlockGraph`.

    This strategy requires specifying the 3D positions of each vertex explicitly
    in the ZX graph. Then the conversion converts each vertex by looking at its
    nearest neighbors to infer the cube and pipe kind. The conversion maps each
    vertex to a cube in the block graph and each edge to a pipe connecting the
    corresponding cubes.

    The conversion process is as follows:

    1. Construct blocks for all the L/T/X-shape subgraphs in the ZX graph.
    2. Construct pipes connecting ports/Y to ports/Y nodes.
    3. Greedily construct the pipes until no more pipes can be inferred.
    4. If there are still nodes left, then choose orientation for an arbitrary node
       and repeat step 3 and 4 until all nodes are handled or conflicts are detected.

    Args:
        g: The positioned ZX graph to be converted to a block graph.

    Returns:
        The :py:class:`~tqec.computation.block_graph.BlockGraph` object
        converted from the ZX graph.

    Raises:
        TQECError: A valid block graph cannot be constructed.

    """
    nodes_to_handle = set(g.g.vertices())
    edges_to_handle = set(g.g.edges())

    bg = BlockGraph()
    # 1. Construct cubes for all the corner nodes in the ZX graph.
    _handle_corners(g, bg, nodes_to_handle)

    # 2. Construct pipes connecting ports/Y to ports/Y nodes.
    _handle_special_pipes(g, bg, nodes_to_handle, edges_to_handle)

    # 3. Greedily construct the pipes until no more pipes can be inferred.
    _greedily_construct_blocks(g, bg, nodes_to_handle, edges_to_handle)

    # 4. If there are still nodes left, then choose orientation for an arbitrary node
    # and repeat 3. Repeat 4 until all nodes are handled or conflicts are detected.
    _handle_leftover_nodes(g, bg, nodes_to_handle, edges_to_handle)

    # Sanity check for the block graph
    bg.validate()
    return bg


def _handle_corners(pg: PositionedZX, bg: BlockGraph, nodes_to_handle: set[int]) -> None:
    g = pg.g
    for v in g.vertices():
        directions = {pg.get_direction(u, v) for u in g.neighbors(v)}
        if len(directions) != 2:
            continue
        normal_direction = set(Direction3D.all_directions()).difference(directions).pop()
        normal_direction_basis = Basis.Z if g.type(v) == zx.VertexType.Z else Basis.X
        bases = [normal_direction_basis.flipped() for _ in range(3)]
        bases[normal_direction.value] = normal_direction_basis
        kind = ZXCube(*bases)
        bg.add_cube(pg[v], kind)
        nodes_to_handle.remove(v)


def _handle_special_pipes(
    pg: PositionedZX,
    bg: BlockGraph,
    nodes_to_handle: set[int],
    edges_to_handle: set[tuple[int, int]],
) -> None:
    g = pg.g

    for edge in set(edges_to_handle):
        u, v = edge
        if is_zx_no_phase(g, u) or is_zx_no_phase(g, v):
            continue
        cube_u = _port_or_y_cube(pg, u)
        cube_v = _port_or_y_cube(pg, v)
        bg.add_cube(cube_u.position, cube_u.kind, cube_u.label)
        bg.add_cube(cube_v.position, cube_v.kind, cube_v.label)
        pipe_kind = _choose_arbitrary_pipe_kind(pg, edge)
        bg.add_pipe(cube_u.position, cube_v.position, pipe_kind)
        nodes_to_handle.remove(u)
        nodes_to_handle.remove(v)
        edges_to_handle.remove(edge)


def _greedily_construct_blocks(
    pg: PositionedZX,
    bg: BlockGraph,
    nodes_to_handle: set[int],
    edges_to_handle: set[tuple[int, int]],
) -> None:
    num_nodes_left = len(nodes_to_handle) + 1
    while len(nodes_to_handle) < num_nodes_left:
        num_nodes_left = len(nodes_to_handle)
        _try_to_handle_edges(pg, bg, nodes_to_handle, edges_to_handle)


def _try_to_handle_edges(
    pg: PositionedZX,
    bg: BlockGraph,
    nodes_to_handle: set[int],
    edges_to_handle: set[tuple[int, int]],
) -> None:
    g = pg.g
    for edge in set(edges_to_handle):
        u, v = edge
        if u in nodes_to_handle and v in nodes_to_handle:
            continue
        ut, vt = g.type(u), g.type(v)
        can_infer_from_u = u not in nodes_to_handle and is_zx_no_phase(g, u)
        can_infer_from_v = v not in nodes_to_handle and is_zx_no_phase(g, v)
        if not can_infer_from_u and not can_infer_from_v:
            continue
        infer_from, other_node = (u, v) if can_infer_from_u else (v, u)
        ipos, opos = pg[infer_from], pg[other_node]
        cube_kind = cast(ZXCube, bg[ipos].kind)
        pipe_kind = PipeKind._from_cube_kind(
            cube_kind,
            pg.get_direction(u, v),
            can_infer_from_u,
            g.edge_type(edge) == zx.EdgeType.HADAMARD,
        )
        other_cube: Cube
        if is_zx_no_phase(g, other_node):
            other_cube_kind = _infer_cube_kind_from_pipe(
                pipe_kind, not can_infer_from_u, vt if can_infer_from_u else ut
            )
            # Check cube kind conflicts
            if other_node not in nodes_to_handle:
                existing_kind = bg[opos].kind
                if not other_cube_kind == existing_kind:
                    raise TQECError(f"Encounter conflicting cube kinds at {opos}: ")
            other_cube = Cube(opos, other_cube_kind)
        else:
            other_cube = _port_or_y_cube(pg, other_node)
        if other_node in nodes_to_handle:
            bg.add_cube(other_cube.position, other_cube.kind, other_cube.label)
            nodes_to_handle.remove(other_node)
        bg.add_pipe(ipos, opos, pipe_kind)
        edges_to_handle.remove(edge)


def _fix_kind_for_one_node(
    pg: PositionedZX,
    bg: BlockGraph,
    nodes_to_handle: set[int],
) -> None:
    g = pg.g
    sorted_nodes = sorted(nodes_to_handle, key=lambda n: pg[n])
    fix_node = next(n for n in sorted_nodes if is_zx_no_phase(g, n))
    fix_pos = pg[fix_node]
    fix_type = g.type(fix_node)
    # Special case: single node ZXGraph
    if g.vertex_degree(fix_node) == 0:
        specified_kind = (
            ZXCube.from_str("ZXZ") if fix_type == zx.VertexType.X else ZXCube.from_str("ZXX")
        )
    else:
        # the basis along the edge direction must be the opposite of the node kind
        basis = ["X", "Z"]
        neighbor = next(iter(g.neighbors(fix_node)))
        basis.insert(
            pg.get_direction(fix_node, neighbor).value,
            "X" if fix_type == zx.VertexType.Z else "Z",
        )
        specified_kind = ZXCube.from_str("".join(basis))
    bg.add_cube(fix_pos, specified_kind)
    nodes_to_handle.remove(fix_node)


def _handle_leftover_nodes(
    pg: PositionedZX,
    bg: BlockGraph,
    nodes_to_handle: set[int],
    edges_to_handle: set[tuple[int, int]],
) -> None:
    while nodes_to_handle:
        _fix_kind_for_one_node(pg, bg, nodes_to_handle)
        _greedily_construct_blocks(pg, bg, nodes_to_handle, edges_to_handle)


def _choose_arbitrary_pipe_kind(pg: PositionedZX, edge: tuple[int, int]) -> PipeKind:
    bases: list[str] = ["X", "Z"]
    direction = pg.get_direction(*edge)
    bases.insert(direction.value, "O")
    if pg.g.edge_type(edge) == zx.EdgeType.HADAMARD:
        bases.append("H")
    return PipeKind.from_str("".join(bases))


def _infer_cube_kind_from_pipe(
    pipe_kind: PipeKind,
    at_pipe_head: bool,
    vertex_type: zx.VertexType,
) -> ZXCube:
    """Infer the cube kinds from the pipe kind."""
    bases = [
        pipe_kind.get_basis_along(direction, at_pipe_head)
        for direction in Direction3D.all_directions()
    ]
    assert vertex_is_zx(vertex_type)
    bases[pipe_kind.direction.value] = Basis.Z if vertex_type == zx.VertexType.X else Basis.X
    return ZXCube(*cast(list[Basis], bases))


def _port_or_y_cube(pg: PositionedZX, v: int) -> Cube:
    g = pg.g
    if is_boundary(g, v):
        if v in g.inputs():
            label = f"IN_{g.inputs().index(v)}"
        elif v in g.outputs():
            label = f"OUT_{g.outputs().index(v)}"
        else:
            label = f"P_{v}"
        return Cube(pg[v], Port(), label)
    return Cube(pg[v], YHalfCube())
