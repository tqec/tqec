from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Iterable
import heapq

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
            return False
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
    obstructed_exits: set[Exit]
    hadamard: bool

    def clone(self) -> Path:
        return Path(
            nodes=list(self.nodes),
            edge_orientations=list(self.edge_orientations),
            obstructed_exits=set(self.obstructed_exits),
            hadamard=self.hadamard,
        )

    @property
    def weight(self) -> int:
        return len(self.nodes) + len(self.obstructed_exits)

    @property
    def last(self) -> Position3D:
        return self.nodes[-1]

    @property
    def edges(self) -> dict[frozenset[Position3D], bool]:
        edges = {
            frozenset({self.nodes[i], self.nodes[i + 1]}): False
            for i in range(len(self.nodes) - 1)
        }
        if self.hadamard:
            edges[frozenset({self.nodes[0], self.nodes[1]})] = True
        return edges

    def grow_to(
        self,
        position: Position3D,
        obstructed_exits: set[Exit],
    ) -> None:
        assert position.is_neighbour(self.nodes[-1])
        # Infer the orientation if not provided
        assert len(self.nodes) > 1
        direction = Direction3D.from_neighbouring_positions(self.nodes[-1], position)
        last_orientation = self.edge_orientations[-1]
        last_direction = Direction3D.from_neighbouring_positions(
            self.nodes[-2], self.nodes[-1]
        )
        if {direction, last_direction} == set(Direction3D.spatial_directions()):
            orientation = not last_orientation
        else:
            orientation = last_orientation

        self.nodes.append(position)
        self.edge_orientations.append(orientation)
        self.obstructed_exits.update(obstructed_exits)


def greedy_bfs_block_synthesis(g: GraphS, random_seed: int | None = None) -> BlockGraph:
    # Try to normalize the input graph
    g = _normalize(g)
    # Nodes and edges left to handle
    nodes_to_handle = {v for v in g.vertex_set() if not is_boundary(g, v)}
    edges_to_handle = {frozenset(e) for e in g.edge_set()}
    edges_left: dict[int, int] = {v: g.vertex_degree(v) for v in nodes_to_handle}
    node_positions: dict[int, Position3D] = {}
    exits: dict[int, list[Exit]] = {}
    position_to_vtype: dict[Position3D, VertexType] = {}

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
                end_is_x_node=is_x_no_phase(g, target),
                hadamard=is_hardmard(g, (v, target)),
                layout=layout,
                node_positions=node_positions,
                exits=exits,
                edges_left=edges_left,
            )
            # obstruct the exits
            exits = {
                node: [e for e in es if e not in path.obstructed_exits]
                for node, es in exits.items()
            }
            edges_left[v] = edges_left[v] - 1
            edges_left[target] = edges_left[target] - 1
            layout.update(path.nodes)
            layout_edges.update(path.edges)
            position_to_vtype.update(_path_nodes_vertex_types(path))
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
        position_to_vtype[v_position] = VertexType.BOUNDARY
    position_to_vtype.update({pos: g.type(i) for i, pos in node_positions.items()})

    # Construct a new zx graph with a mapping from vertex to position
    layout_zx = GraphS()
    v2p: dict[int, Position3D] = {}
    for pos, vtype in position_to_vtype.items():
        n = layout_zx.add_vertex(vtype)
        v2p[n] = pos
    p2v = {v: p for p, v in v2p.items()}
    for p1, p2 in layout_edges:
        n1, n2 = p2v[p1], p2v[p2]
        edge_type = (
            EdgeType.HADAMARD if layout_edges[frozenset({p1, p2})] else EdgeType.SIMPLE
        )
        layout_zx.add_edge((n1, n2), edge_type)
    # Synthesize the block graph
    # for v in layout_zx.vertex_set():
    #     print(v, layout_zx.type(v).name, v2p[v])
    return positioned_block_synthesis(PositionedZX(layout_zx, v2p))


def _bfs_min_weight_path_allocate_end(
    start: int,
    end: int,
    end_is_x_node: bool,
    hadamard: bool,
    layout: set[Position3D],
    node_positions: dict[int, Position3D],
    exits: dict[int, list[Exit]],
    edges_left: dict[int, int],
) -> Path:
    start_pos = node_positions[start]
    exits_set = set(chain(*exits.values()))
    min_weight_path: Path | None = None
    path_end_exits: list[Exit] = []
    queue: list[Path] = []
    for exit in exits[start]:
        path = Path(
            [start_pos, exit.to_position],
            [exit.orientation ^ hadamard],
            {exit},
            hadamard,
        )
        queue.append(path)
    while queue:
        path = queue.pop(0)
        end_exits = _exits_of_new_allocation(
            position=path.last,
            reach_from=path.nodes[-2],
            edge_orientation=path.edge_orientations[-1],
            is_x_node=end_is_x_node,
            exits_set=exits_set.difference(path.obstructed_exits),
            allocations=layout | set(path.nodes[:-1]),
        )
        if len(end_exits) >= edges_left[end] - 1:
            if min_weight_path is None or path.weight < min_weight_path.weight:
                min_weight_path = path
                path_end_exits = end_exits
            continue
        for dir in SignedDirection3D.all_directions():
            next_pos = path.last.shift_in_direction(
                dir.direction, 1 if dir.towards_positive else -1
            )
            if next_pos in layout or next_pos in path.nodes:
                continue
            new_path = path.clone()
            obstructed_by_next_pos = {
                exit for exit in exits_set if exit.is_obstructed_by_position(next_pos)
            }
            new_path.grow_to(next_pos, obstructed_by_next_pos)
            prune: bool = False
            for node, es in exits.items():
                num_edges = edges_left[node]
                num_exits = len([e for e in es if e not in new_path.obstructed_exits])
                if num_exits < num_edges:
                    prune = True
                    break
            if prune:
                continue
            if min_weight_path is None or new_path.weight < min_weight_path.weight:
                queue.append(new_path)
    if min_weight_path is None:
        raise TQECException(f"Could not find a path from {start} to {end}.")
    # allocate the end node
    node_positions[end] = min_weight_path.last
    exits[end] = path_end_exits
    return min_weight_path


def _bfs_min_weight_path(
    start: int,
    end: int,
    end_is_x_node: bool,
    hadamard: bool,
    layout: set[Position3D],
    node_positions: dict[int, Position3D],
    exits: dict[int, list[Exit]],
    edges_left: dict[int, int],
) -> Path:
    if end not in node_positions:
        return _bfs_min_weight_path_allocate_end(
            start=start,
            end=end,
            end_is_x_node=end_is_x_node,
            hadamard=hadamard,
            layout=layout,
            node_positions=node_positions,
            exits=exits,
            edges_left=edges_left,
        )

    # If the end node has already been placed
    start_pos = node_positions[start]
    end_pos = node_positions[end]
    exits_set = set(chain(*exits.values()))
    min_weight_path: Path | None = None
    tie_breaker = 0
    queue = []
    for exit in exits[start]:
        path = Path(
            [start_pos, exit.to_position],
            [exit.orientation ^ hadamard],
            {exit},
            hadamard,
        )
        heuristic = min(
            exit.to_position.manhattan_distance(ee.to_position) for ee in exits[end]
        )
        priority = path.weight + heuristic
        heapq.heappush(queue, (priority, tie_breaker, path))
        tie_breaker += 1

    while queue:
        _, _, path = heapq.heappop(queue)

        if path.last == end_pos:
            # orientation is correct
            expected_orientation = path.edge_orientations[-1]
            expected_exit = Exit(
                end_pos,
                SignedDirection3D.from_neighbouring_positions(end_pos, path.nodes[-2]),
                expected_orientation,
            )
            if expected_exit in exits[end]:
                if (
                    min_weight_path is not None
                    and path.weight >= min_weight_path.weight
                ):
                    continue
                prune = False
                for node, es in exits.items():
                    num_edges = edges_left[node]
                    if node == end:
                        num_edges -= 1
                    num_exits = len([e for e in es if e not in path.obstructed_exits])
                    if num_exits < num_edges:
                        prune = True
                        break
                if not prune:
                    min_weight_path = path
            continue
        for dir in SignedDirection3D.all_directions():
            next_pos = path.last.shift_in_direction(
                dir.direction, 1 if dir.towards_positive else -1
            )
            if next_pos in path.nodes:
                continue
            if next_pos in layout and next_pos != end_pos:
                continue
            new_path = path.clone()
            obstructed_by_next_pos = {
                exit for exit in exits_set if exit.is_obstructed_by_position(next_pos)
            }
            new_path.grow_to(next_pos, obstructed_by_next_pos)
            heuristic = min(
                new_path.last.manhattan_distance(ee.to_position) for ee in exits[end]
            )
            w = new_path.weight + heuristic
            if min_weight_path is None or w < min_weight_path.weight:
                heapq.heappush(queue, (w, tie_breaker, new_path))
                tie_breaker += 1
    if min_weight_path is None:
        raise TQECException(f"Could not find a path from {start} to {end}.")
    return min_weight_path


def _exits_of_new_allocation(
    position: Position3D,
    reach_from: Position3D,
    edge_orientation: bool,
    is_x_node: bool,
    exits_set: set[Exit],
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
        position, reach_from
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
            if any(
                potential_exit.is_obstructed_by_position(pos) for pos in allocations
            ):
                continue
            if any(potential_exit.is_obstructed_by_exit(exit) for exit in exits_set):
                continue
            exits.append(potential_exit)
    return exits


def _path_nodes_vertex_types(path: Path) -> dict[Position3D, VertexType]:
    if len(path.nodes) == 2:
        return {}
    ret = {}
    for i in range(len(path.nodes) - 2):
        node = path.nodes[i + 1]
        d1 = Direction3D.from_neighbouring_positions(path.nodes[i], node)
        d2 = Direction3D.from_neighbouring_positions(node, path.nodes[i + 2])
        o = path.edge_orientations[i]
        if d1 == d2:
            ret[node] = VertexType.Z
        elif {d1, d2} == {Direction3D.X, Direction3D.Y}:
            ret[node] = VertexType.X if (o ^ (d1 == Direction3D.X)) else VertexType.Z
        elif {d1, d2} == {Direction3D.X, Direction3D.Z}:
            ret[node] = VertexType.X if o else VertexType.Z
        else:
            ret[node] = VertexType.Z if o else VertexType.X
    return ret


def _normalize(g: GraphS) -> GraphS:
    """Try to normalize the graph and make it have the following properties:
    1) Normal edges only connect nodes of the opposite color
    2) Hadamard edges only connect nodes of the same color
    3) No self edges
    4) No multi-edges
    5) No nodes with degree >= 5
    """
    return g
