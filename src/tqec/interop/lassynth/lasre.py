import json
from pathlib import Path
from typing import Any
from itertools import product

import networkx as nx

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import ZXCube
from tqec.computation.pipe import PipeKind
from tqec.utils.enums import Basis
from tqec.utils.position import Direction3D, Position3D


def convert_lasre_to_block_graph(lasre_filepath: str | Path) -> BlockGraph:
    """Read a LASRe file and convert it to a BlockGraph."""
    # LaSre file is actually a JSON file
    with open(lasre_filepath) as f:
        lasre: dict[str, Any] = json.load(f)

    g = nx.Graph()
    for i, port in enumerate(lasre["port_cubes"]):
        g.add_node(Position3D(*port), is_port=True, is_y=False)

    ijk_iter = list(
        product(range(lasre["n_i"]), range(lasre["n_j"]), range(lasre["n_k"]))
    )
    y_predicates = lasre["NodeY"]
    # At first, we add all the cubes MIGHT EXIST in the bounding box
    for i, j, k in ijk_iter:
        pos = Position3D(i, j, k)
        if pos in g.nodes:
            continue
        g.add_node(Position3D(i, j, k), is_port=False, is_y=y_predicates[i][j][k] == 1)
    # Add edges
    for key, direction in zip(
        ["ExistI", "ExistJ", "ExistK"], Direction3D.all_directions()
    ):
        for i, j, k in ijk_iter:
            if lasre[key][i][j][k]:
                u, v = (
                    Position3D(i, j, k),
                    Position3D(i, j, k).shift_in_direction(direction, 1),
                )
                g.add_edge(
                    u,
                    v,
                    direction=direction,
                    basis={
                        u: [None] * 3,
                        v: [None] * 3,
                    },
                )
    # Remove all the isolated nodes
    g.remove_nodes_from(list(nx.isolates(g)))

    # Resolve the basis
    # The ports that have basis specified
    for port_attr, port in zip(lasre["ports"], lasre["port_cubes"]):
        d: str = port_attr["d"]
        c: int = port_attr["c"]
        z_basis_direction = ("IJK".index(d) + (-1 if c else 1)) % 3
        pos = Position3D(*port)
        edge = next(iter(g.edges(pos)))
        edge_data = g.edges[edge]
        basis = edge_data["basis"][pos]
        basis[z_basis_direction] = Basis.Z
        x_basis_direction = (
            set(Direction3D.all_directions())
            - {
                Direction3D(z_basis_direction),
                edge_data["direction"],
            }
        ).pop()
        basis[x_basis_direction.value] = Basis.X
        _set_basis_at(g, pos, edge, basis)

    # Start from a single port and color the graph progressively
    start = Position3D(*lasre["port_cubes"][0])
    for edge in nx.edge_bfs(g, start):
        if _resolved(g, edge):
            continue
        ed = _direction(g, edge)
        for n in edge:
            if _resolved_at(g, n, edge):
                continue
            # Infer the basis based on the color matching rules
            for neighbour in g.edges(n):
                if not _resolved_at(g, n, neighbour):
                    continue
                basis_neighbor = _basis_at(g, n, neighbour)
                ndir = _direction(g, neighbour)
                inferred_basis: list[Basis | None] = [None] * 3
                if ndir == ed:
                    inferred_basis = list(basis_neighbor)
                else:
                    inferred_basis[(ed.value + 1) % 3] = basis_neighbor[
                        (ndir.value + 2) % 3
                    ]
                    inferred_basis[(ed.value + 2) % 3] = basis_neighbor[
                        (ndir.value + 1) % 3
                    ]
                _set_basis_at(g, n, edge, inferred_basis)
                break
        if _resolved(g, edge):
            continue
        assert any(
            _resolved_at(g, n, edge) for n in edge
        ), f"at least one end should be resolved, but not for {edge}"
        # Cannot infer the basis, so we just assign the basis as the same as the
        # resolved end
        u, v = edge
        resolved, not_resolved = (u, v) if _resolved_at(g, u, edge) else (v, u)
        resolved_basis = _basis_at(g, resolved, edge)
        _set_basis_at(g, not_resolved, edge, resolved_basis)

    unresolved_edges = [edge for edge in g.edges if not _resolved(g, edge)]
    assert (
        len(unresolved_edges) == 0
    ), f"There are unresolved edges left: {unresolved_edges}"

    bg = BlockGraph()
    # Resolve cube basis
    pid = 0
    for node, data in g.nodes(data=True):
        if data["is_port"]:
            bg.add_cube(node, "P", f"P_{pid}")
            pid += 1
            continue
        if data["is_y"]:
            bg.add_cube(node, "Y")
            continue
        basis: list[Basis | None] = [None] * 3
        for neighbour in g.edges(node):
            basis_at_node = _basis_at(g, node, neighbour)
            for i, b in enumerate(basis_at_node):
                if b is not None:
                    assert (
                        basis[i] is None or basis[i] == b
                    ), f"Conflicting basis at node {node}"
                    basis[i] = b
        basis_zx = [b if b is not None else Basis.Z for b in basis]
        bg.add_cube(node, ZXCube(*basis_zx))

    for edge in g.edges:
        u, v = edge
        u, v = min(u, v), max(u, v)
        basis_u = _basis_at(g, u, edge)
        basis_v = _basis_at(g, v, edge)
        has_hadamard = any(b1 != b2 for b1, b2 in zip(basis_u, basis_v))
        pipe_kind = PipeKind(*basis_u, has_hadamard=has_hadamard)
        bg.add_pipe(u, v, pipe_kind)

    return bg


def _direction(g: nx.Graph, edge: tuple[Position3D, Position3D]) -> Direction3D:
    return g.edges[edge]["direction"]


def _basis_at(
    g: nx.Graph, n: Position3D, edge: tuple[Position3D, Position3D]
) -> list[Basis | None]:
    data = g.edges[edge]
    return data["basis"][n]


def _set_basis_at(
    g: nx.Graph,
    n: Position3D,
    edge: tuple[Position3D, Position3D],
    basis: list[Basis | None],
) -> None:
    basis_data = g.edges[edge]["basis"]
    basis_data[n] = basis  # type: ignore
    g[edge[0]][edge[1]]["basis"] = basis_data


def _resolved(g: nx.Graph, edge: tuple[Position3D, Position3D]) -> bool:
    return _resolved_at(g, edge[0], edge) and _resolved_at(g, edge[1], edge)


def _resolved_at(
    g: nx.Graph, n: Position3D, edge: tuple[Position3D, Position3D]
) -> bool:
    basis = _basis_at(g, n, edge)
    return not all(b is None for b in basis)
