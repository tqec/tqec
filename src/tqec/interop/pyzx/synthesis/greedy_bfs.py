from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from typing import Iterable
import numpy as np
from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D, SignedDirection3D
from tqec.interop.pyzx.utils import (
    is_hardmard,
    is_boundary,
    is_x_no_phase,
)
from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis


@dataclass(frozen=True)
class Exit:
    position: Position3D
    beam: SignedDirection3D
    orientation: bool

    @property
    def to_position(self) -> Position3D:
        return self.position.shift_in_direction(
            self.beam.direction, 1 if self.beam.towards_positive else -1
        )

    def is_obstructed_by_position(self, position: Position3D) -> bool:
        if self.position == position:
            raise TQECException("Cannot check obstruction with the same position.")
        beam_dir = self.beam.direction
        p1, p2 = self.position, position
        return (
            all(
                p1.at_direction(dir) == p2.at_direction(dir)
                for dir in beam_dir.orthogonal_directions
            )
            and ((p2.at_direction(beam_dir) - p1.at_direction(beam_dir)) > 0)
            == self.beam.towards_positive
        )

    def is_obstructed_by_exit(self, exit: Exit) -> bool:
        d1, d2 = self.beam, exit.beam
        p1, p2 = self.position, exit.position
        if d1.direction == d2.direction:
            if any(
                p1.at_direction(dir) != p2.at_direction(dir)
                for dir in d1.direction.orthogonal_directions
            ):
                return False
            return (
                (p2.at_direction(d1.direction) - p1.at_direction(d1.direction)) > 0
            ) == d1.towards_positive

        beam_plane = {self.beam.direction, exit.beam.direction}
        normal_dir = next(
            dir for dir in Direction3D.all_directions() if dir not in beam_plane
        )
        if p1.at_direction(normal_dir) != p2.at_direction(normal_dir):
            return False
        t = (p2.at_direction(d1.direction) - p1.at_direction(d1.direction)) * (
            1 if d1.towards_positive else -1
        )
        s = (p1.at_direction(d2.direction) - p2.at_direction(d2.direction)) * (
            1 if d2.towards_positive else -1
        )
        return t > 0 and s > 0


@dataclass
class Path:
    nodes: list[Position3D]
    edge_orientations: list[bool]
    edge_hadamard: list[bool]

    @property
    def edges(self) -> dict[frozenset[Position3D], bool]:
        return {
            frozenset({self.nodes[i], self.nodes[i + 1]}): self.edge_hadamard[i]
            for i in range(len(self.nodes) - 1)
        }

    def grow_to(
        self,
        position: Position3D,
        hadamard: bool = False,
        initial_orientation: bool | None = None,
    ) -> None:
        assert position.is_neighbour(self.nodes[-1])
        # Infer the orientation if not provided
        if initial_orientation is None:
            assert len(self.nodes) > 1
            direction = Direction3D.from_neighbouring_positions(
                self.nodes[-1], position
            )
            last_orientation = self.edge_orientations[-1]
            last_direction = Direction3D.from_neighbouring_positions(
                self.nodes[-2], self.nodes[-1]
            )
            if direction == last_direction:
                orientation = last_orientation
            else:
                orientation = not last_orientation
        else:
            orientation = initial_orientation

        self.edge_orientations.append(orientation ^ hadamard)
        self.edge_hadamard.append(hadamard)


def greedy_bfs_block_synthesis(g: GraphS, random_seed: int | None = None) -> BlockGraph:
    # Try to normalize the input graph
    g = _normalize(g)
    # Nodes and edges left to handle
    nodes_to_handle = {v for v in g.vertex_set() if not is_boundary(g, v)}
    edges_to_handle = {frozenset(e) for e in g.edge_set()}
    edges_left: dict[int, int] = {v: g.degree(v) for v in nodes_to_handle}
    node_positions: dict[int, Position3D] = {}
    exits: defaultdict[int, list[Exit]] = defaultdict(list)

    # 3D layout of the zx graph
    layout: set[Position3D] = set()
    layout_edges: dict[frozenset[Position3D], bool] = {}

    # Choose a node to start with
    root = min(nodes_to_handle)
    if random_seed is not None:
        rng = np.random.default_rng(random_seed)
        root = int(rng.choice(list(nodes_to_handle), 0).item())
    # set the root node at the origin
    root_pos = Position3D(0, 0, 0)
    layout.add(root_pos)
    node_positions[root] = root_pos
    root_exits = []
    for dir in Direction3D.spatial_directions():
        for sign in [True, False]:
            orientation = is_x_no_phase(g, root) ^ (dir == Direction3D.X)
            root_exits.append(Exit(root_pos, SignedDirection3D(dir, sign), orientation))
    exits[root] = root_exits
    nodes_to_handle.remove(root)

    # Start the outer BFS in the zx graph
    queue: list[int] = [root]
    visited: set[int] = set()
    while queue:
        v = queue.pop(0)
        visited.add(v)
        for target in g.neighbors(v):
            # Leave the boundary nodes till the end
            if is_boundary(g, target):
                continue
            # The node and edge have already been handled
            if frozenset({v, target}) not in edges_to_handle:
                continue
            path = _bfs_min_weight_path(
                start=v,
                end=target,
                hadamard=is_hardmard(g, (v, target)),
                layout=layout,
                node_positions=node_positions,
                exits=exits,
                edges_left=edges_left,
            )
            layout.update(path.nodes)
            layout_edges.update(path.edges)
            edges_to_handle.remove(frozenset({v, target}))
            if target in nodes_to_handle:
                nodes_to_handle.remove(target)
            if target not in visited:
                queue.append(target)
    # Handle Boundary nodes and edges
    boundary_nodes = {v for v in g.vertex_set() if is_boundary(g, v)}
    for v in boundary_nodes:
        edge = next(g.edges(v))
        u = edge[0] if edge[0] != v else edge[1]
        exit = exits[u][0]
        v_position = exit.to_position
        node_positions[v] = v_position
        layout.add(v_position)
        layout_edges[frozenset({node_positions[u], v_position})] = is_hardmard(g, edge)

    # Construct a new zx graph with a mapping from vertex to position
    layout_zx = GraphS()
    v2p: dict[int, Position3D] = {}
    for i, pos in node_positions.items():
        layout.remove(pos)
        n = layout_zx.add_vertex(g.type(i))
        v2p[n] = pos
    for p in layout:
        n = layout_zx.add_vertex(VertexType.Z)
        v2p[n] = p
    p2v = {v: p for p, v in v2p.items()}
    for p1, p2 in layout_edges:
        n1, n2 = p2v[p1], p2v[p2]
        edge_type = (
            EdgeType.HADAMARD if layout_edges[frozenset({p1, p2})] else EdgeType.SIMPLE
        )
        layout_zx.add_edge((n1, n2), edge_type)
    # Synthesize the block graph
    return positioned_block_synthesis(PositionedZX(layout_zx, v2p))


def _bfs_min_weight_path(
    start: int,
    end: int,
    hadamard: bool,
    layout: set[Position3D],
    node_positions: dict[int, Position3D],
    exits: dict[int, list[Exit]],
    edges_left: dict[int, int],
) -> Path:
    # start_pos = node_positions[start]
    # if end not in node_positions:
    #     end_num_edges = edges_left[end] - 1
    pass


def _exits_of_new_allocation(
    position: Position3D,
    reach_from: Position3D,
    edge_orientation: bool,
    is_x_node: bool,
    current_exits: dict[int, list[Exit]],
    allocations: Iterable[Position3D],
) -> list[Exit]:
    edge_direction = Direction3D.from_neighbouring_positions(reach_from, position)
    match edge_orientation, edge_direction, is_x_node:
        case False, Direction3D.X, True:
            normal_direction = Direction3D.Z
        case False, _, True:
            normal_direction = Direction3D.X
        case True, Direction3D.Y, True:
            normal_direction = Direction3D.Z
        case True, _, True:
            normal_direction = Direction3D.Y
        case False, Direction3D.Y, False:
            normal_direction = Direction3D.Z
        case False, _, False:
            normal_direction = Direction3D.Y
        case True, Direction3D.X, False:
            normal_direction = Direction3D.Z
        case True, _, False:
            normal_direction = Direction3D.X

    edge_signed_dir = SignedDirection3D.from_neighbouring_positions(
        reach_from, position
    )
    exits: list[Exit] = []

    for dir in normal_direction.orthogonal_directions:
        for sign in [True, False]:
            signed_direction = SignedDirection3D(dir, sign)
            if signed_direction == edge_signed_dir:
                continue
            orientation = edge_orientation
            if {edge_direction, dir} == set(Direction3D.spatial_directions()):
                orientation = not orientation
            potential_exit = Exit(position, signed_direction, orientation)
            # Check obstruction
            for position in allocations:
                if potential_exit.is_obstructed_by_position(position):
                    continue
            for exit in chain(*current_exits.values()):
                if potential_exit.is_obstructed_by_exit(exit):
                    continue
            exits.append(potential_exit)
    return exits


def _normalize(g: GraphS) -> GraphS:
    """Try to normalize the graph and make it have the following properties:
    1) Normal edges only connect nodes of the opposite color
    2) Hadamard edges only connect nodes of the same color
    3) No self edges
    4) No multi-edges
    5) No nodes with degree >= 5
    """
    return g
