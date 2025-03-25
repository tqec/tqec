from __future__ import __annotations__

from dataclasses import dataclass
import numpy as np
from pyzx.graph.graph_s import GraphS

from tqec.computation.block_graph import BlockGraph
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D, SignedDirection3D
from tqec.interop.pyzx.utils import is_x_no_phase, is_z_no_phase, is_boundary


@dataclass(frozen=True)
class Exit:
    position: Position3D
    beam: SignedDirection3D
    x_orientation: Direction3D

    def is_obstructed_by_position(self, position: Position3D) -> bool:
        if self.position == position:
            raise TQECException("Cannot check obstruction with the same position.")
        beam_dir = self.beam.direction
        p1 = self.position.as_tuple()
        p2 = position.as_tuple()
        return (
            all(p1[dir.value] == p2[dir.value] for dir in Direction3D.all_directions())
            and ((p2[beam_dir.value] - p1[beam_dir.value]) > 0)
            == self.beam.towards_positive
        )

    def is_obstructed_by_exit(self, exit: "Exit") -> bool:
        pass


def greedy_bfs_block_synthesis(g: GraphS, random_seed: int | None = None) -> BlockGraph:
    # Try to normalize the input graph
    g = _normalize(g)
    nodes = {v for v in g.vertex_set() if not is_boundary(g, v)}
    edges_left: dict[int, int] = {v: g.degree(v) for v in nodes}

    layout_g = GraphS()
    positions: dict[int, Position3D] = {}
    exits: dict[int, list[Exit]] = {}
    # Choose a node to start with
    root = min(nodes)
    if random_seed is not None:
        rng = np.random.default_rng(random_seed)
        root = int(rng.choice(list(nodes), 0).item())
    root_pos = Position3D(0, 0, 0)
    layout_g.add_vertex_indexed(root)
    layout_g.set_type(root, g.type(root))
    positions[root] = root_pos
    root_exits = []
    for dir in Direction3D.spatial_directions():
        for sign in [True, False]:
            if is_x_no_phase(g, root):
                x_orientation = Direction3D.Z
            else:
                x_orientation = next(
                    d for d in dir.orthogonal_directions if d != Direction3D.Z
                )
            root_exits.append(
                Exit(root_pos, SignedDirection3D(dir, sign), x_orientation)
            )
    exits[root] = root_exits

    # Start the outer BFS in the zx graph
    queue = [root]
    visited = {root}
    while queue:
        v = queue.pop(0)
        for target in g.neighbors(v):
            if target in visited:
                continue
            # Leave the boundary nodes till the end
            if is_boundary(g, target):
                continue
            visited.add(target)
            queue.append(target)
            # Inner BFS for all the exits
            for exit in exits[v]:
                pass


def _normalize(g: GraphS) -> GraphS:
    """Try to normalize the graph and make it have the following properties:
    1) Normal edges only connect nodes of the opposite color
    2) Hadamard edges only connect nodes of the same color
    3) No self edges
    4) No multi-edges
    5) No nodes with degree >= 5
    """
    return g
