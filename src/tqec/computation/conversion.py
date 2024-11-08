"""Conversion between ``ZXGraph`` and ``BlockGraph``."""

from typing import cast
from tqec.computation.cube import (
    Cube,
    CubeKind,
    Port,
    YCube,
    ZXBasis,
    ZXCube,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.pipe import PipeKind
from tqec.computation.zx_graph import ZXEdge, ZXGraph, ZXKind, ZXNode
from tqec.exceptions import TQECException
from tqec.position import Direction3D


def convert_block_graph_to_zx_graph(
    block_graph: BlockGraph, name: str | None = None
) -> ZXGraph:
    """Convert a :py:class:`~tqec.computation.block_graph.BlockGraph` to a
    :py:class:`~tqec.computation.zx_graph.ZXGraph`.

    The conversion process is as follows:

    1. For each cube in the block graph, convert it to a ZX node by calling :py:meth:`~tqec.computation.cube.Cube.to_zx_node`.
    2. For each pipe in the block graph, add an edge to the ZX graph with the corresponding endpoints and Hadamard flag.

    Args:
        block_graph: The block graph to be converted to a ZX graph.
        name: The name of the new ZX graph. If None, the name of the block graph will be used.

    Returns:
        The :py:class:`~tqec.computation.zx_graph.ZXGraph` object converted from the block graph.
    """

    zx_graph = ZXGraph(name or block_graph.name)
    for cube in block_graph.nodes:
        zx_graph.add_node(cube.to_zx_node())
    for pipe in block_graph.edges:
        zx_graph.add_edge(
            pipe.u.to_zx_node(), pipe.v.to_zx_node(), pipe.kind.has_hadamard
        )
    return zx_graph


def convert_zx_graph_to_block_graph(
    zx_graph: ZXGraph, name: str | None = None
) -> BlockGraph:
    """Convert a :py:class:`~tqec.computation.zx_graph.ZXGraph` to a
    :py:class:`~tqec.computation.block_graph.BlockGraph`.

    Currently, the conversion respects the explicit 3D structure of the ZX graph. And convert node by node, edge by edge.
    Future work may include automatic compilation from a simplified or a more general ZX diagram to a block graph implementation.

    To successfully convert a ZX graph to a block graph, the following necessary conditions must be satisfied:

    - The ZX graph itself is a valid representation, i.e. :py:meth:`~tqec.computation.zx_graph.ZXGraph.check_invariants` does not raise an exception.
    - Every nodes in the ZX graph connects to edges at most in two directions, i.e. there is no 3D corner node.
    - Y nodes in the ZX graph can only have edges in time direction.

    The conversion process is as follows:

    1. Construct cubes for all the corner nodes in the ZX graph.
    2. Construct pipes connecting ports/Y to ports/Y nodes.
    3. Greedily construct the pipes until no more pipes can be inferred.
    4. If there are still nodes left, then choose orientation for an arbitrary node
       and repeat step 3 and 4 until all nodes are handled or conflicts are detected.

    Args:
        zx_graph: The ZX graph to be converted to a block graph.
        name: The name of the new block graph. If None, the name of the ZX graph will be used.

    Returns:
        The :py:class:`~tqec.computation.block_graph.BlockGraph` object converted from the ZX graph.

    Raises:
        TQECException: If the ZX graph does not satisfy the necessary conditions
            or there are inference conflicts during the conversion.
    """
    # Check necessary conditions
    zx_graph.check_invariants()
    for node in zx_graph.nodes:
        if len({e.direction for e in zx_graph.edges_at(node.position)}) == 3:
            raise TQECException(f"ZX graph has a 3D corner at {node.position}.")
        if node.is_y_node:
            (edge,) = zx_graph.edges_at(node.position)
            if not edge.direction == Direction3D.Z:
                raise TQECException("The Y node must only has Z-direction edge.")

    nodes_to_handle = set(zx_graph.nodes)
    edges_to_handle = set(zx_graph.edges)

    block_graph = BlockGraph(name or zx_graph.name)
    # 1. Construct cubes for all the corner nodes in the ZX graph.
    _handle_corners(zx_graph, block_graph, nodes_to_handle)

    # 2. Construct pipes connecting ports/Y to ports/Y nodes.
    _handle_special_pipes(block_graph, nodes_to_handle, edges_to_handle)

    # 3. Greedily construct the pipes until no more pipes can be inferred.
    _greedily_construct_blocks(block_graph, nodes_to_handle, edges_to_handle)

    # 4. If there are still nodes left, then choose orientation for an arbitrary node
    # and repeat 3. Repeat 4 until all nodes are handled or conflicts are detected.
    _handle_leftover_nodes(zx_graph, block_graph, nodes_to_handle, edges_to_handle)

    block_graph.validate()
    return block_graph


def _handle_corners(
    zx_graph: ZXGraph, block_graph: BlockGraph, nodes_to_handle: set[ZXNode]
) -> None:
    for node in zx_graph.nodes:
        directions = {e.direction for e in zx_graph.edges_at(node.position)}
        if len(directions) != 2:
            continue
        normal_direction = (
            set(Direction3D.all_directions()).difference(directions).pop()
        )
        kind = ZXCube.from_normal_basis(ZXBasis(node.kind.value), normal_direction)
        block_graph.add_node(Cube(node.position, kind, node.label))
        nodes_to_handle.remove(node)


def _handle_special_pipes(
    block_graph: BlockGraph,
    nodes_to_handle: set[ZXNode],
    edges_to_handle: set[ZXEdge],
) -> None:
    for edge in set(edges_to_handle):
        u, v = edge.u, edge.v
        if u.is_zx_node or v.is_zx_node:
            continue
        pipe_kind = _choose_arbitrary_pipe_kind(edge)
        block_graph.add_edge(
            Cube(u.position, Port() if u.is_port else YCube(), u.label),
            Cube(v.position, Port() if v.is_port else YCube(), v.label),
            pipe_kind,
        )
        nodes_to_handle.remove(u)
        nodes_to_handle.remove(v)
        edges_to_handle.remove(edge)


def _greedily_construct_blocks(
    block_graph: BlockGraph,
    nodes_to_handle: set[ZXNode],
    edges_to_handle: set[ZXEdge],
) -> None:
    num_nodes_left = len(nodes_to_handle) + 1
    while len(nodes_to_handle) < num_nodes_left:
        num_nodes_left = len(nodes_to_handle)
        _try_to_handle_edges(block_graph, nodes_to_handle, edges_to_handle)


def _try_to_handle_edges(
    block_graph: BlockGraph,
    nodes_to_handle: set[ZXNode],
    edges_to_handle: set[ZXEdge],
) -> None:
    for edge in set(edges_to_handle):
        u, v = edge.u, edge.v
        if u in nodes_to_handle and v in nodes_to_handle:
            continue
        can_infer_from_u = u not in nodes_to_handle and u.is_zx_node
        can_infer_from_v = v not in nodes_to_handle and v.is_zx_node
        if not can_infer_from_u and not can_infer_from_v:
            continue
        infer_from, other_node = (u, v) if can_infer_from_u else (v, u)
        cube_kind = cast(ZXCube, block_graph[infer_from.position].kind)
        pipe_kind = PipeKind.from_cube_kind(
            cube_kind, edge.direction, can_infer_from_u, edge.has_hadamard
        )
        other_cube_kind: CubeKind
        if other_node.is_zx_node:
            other_cube_kind = _infer_cube_kind_from_pipe(
                pipe_kind,
                not can_infer_from_u,
                v.kind if can_infer_from_u else u.kind,
            )
            # Check cube kind conflicts
            if other_node not in nodes_to_handle:
                existing_kind = block_graph[other_node.position].kind
                if not other_cube_kind == existing_kind:
                    raise TQECException(
                        f"Encounter conflicting cube kinds at {other_node.position}: "
                    )
        else:
            other_cube_kind = Port() if other_node.is_port else YCube()
        block_graph.add_edge(
            block_graph[infer_from.position],
            Cube(other_node.position, other_cube_kind, other_node.label),
            pipe_kind,
        )
        if other_node in nodes_to_handle:
            nodes_to_handle.remove(other_node)
        edges_to_handle.remove(edge)


def _fix_kind_for_one_node(
    zx_graph: ZXGraph,
    block_graph: BlockGraph,
    nodes_to_handle: set[ZXNode],
) -> None:
    sorted_nodes = sorted(nodes_to_handle, key=lambda n: n.position)
    fix_kind_node = next(n for n in sorted_nodes if n.is_zx_node)
    edges_at_node = zx_graph.edges_at(fix_kind_node.position)
    # Special case: single node ZXGraph
    if len(edges_at_node) == 0:
        specified_kind = (
            ZXCube.from_str("ZXZ")
            if fix_kind_node.kind == ZXKind.X
            else ZXCube.from_str("ZXX")
        )
    else:
        # the basis along the edge direction must be the opposite of the node kind
        basis = ["X", "Z"]
        basis.insert(
            edges_at_node[0].direction.value,
            fix_kind_node.kind.with_zx_flipped().value,
        )
        specified_kind = ZXCube.from_str("".join(basis))
    block_graph.add_node(
        Cube(fix_kind_node.position, specified_kind, fix_kind_node.label)
    )
    nodes_to_handle.remove(fix_kind_node)


def _handle_leftover_nodes(
    zx_graph: ZXGraph,
    block_graph: BlockGraph,
    nodes_to_handle: set[ZXNode],
    edges_to_handle: set[ZXEdge],
) -> None:
    while nodes_to_handle:
        _fix_kind_for_one_node(zx_graph, block_graph, nodes_to_handle)
        _greedily_construct_blocks(block_graph, nodes_to_handle, edges_to_handle)


def _choose_arbitrary_pipe_kind(edge: ZXEdge) -> PipeKind:
    bases: list[str] = ["X", "Z"]
    bases.insert(edge.direction.value, "O")
    if edge.has_hadamard:
        bases.append("H")
    return PipeKind.from_str("".join(bases))


def _infer_cube_kind_from_pipe(
    pipe_kind: PipeKind,
    at_pipe_head: bool,
    node_kind: ZXKind,
) -> ZXCube:
    """Infer the cube kinds from the pipe kind."""
    bases = [
        pipe_kind.get_basis_along(direction, at_pipe_head)
        for direction in Direction3D.all_directions()
    ]
    bases[pipe_kind.direction.value] = ZXBasis(node_kind.value).with_zx_flipped()
    return ZXCube(*cast(list[ZXBasis], bases))
