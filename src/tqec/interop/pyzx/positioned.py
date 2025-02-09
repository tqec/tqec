"""ZX graph with 3D positions."""

from __future__ import annotations

from fractions import Fraction
from typing import Mapping

import pyzx as zx
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from pyzx.graph.graph_s import GraphS

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.utils import cube_kind_to_zx
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D
from tqec.utils.scale import round_or_fail


class PositionedZX:
    def __init__(self, g: GraphS, positions: Mapping[int, Position3D]) -> None:
        """A ZX graph with 3D positions and additional constraints.

        The constraints are:

        1. The vertex IDs in the graph match the position keys exactly.
        2. The neighbors are all shifted by 1 in the 3D positions.
        3. All the spiders are Z(0) or X(0) or Z(1/2) or Boundary spiders.
        4. Boundary and Z(1/2) spiders are dangling, and Z(1/2) connects to the
           time direction.
        5. There are no 3D corners.

        Args:
            g: The ZX graph.
            positions: A dictionary mapping vertex IDs to their 3D positions.

        Raises:
            TQECException: If the constraints are not satisfied.
        """

        self.check_preconditions(g, positions)

        self._g = g
        self._positions: dict[int, Position3D] = dict(positions)

    @staticmethod
    def check_preconditions(g: GraphS, positions: Mapping[int, Position3D]) -> None:
        """Check the preconditions for the ZX graph with 3D positions."""
        # 1. Check the vertex IDs in the graph match the positions
        if g.vertex_set() != set(positions.keys()):
            raise TQECException(
                "The vertex IDs in the ZX graph and the positions do not match."
            )
        # 2. Check the neighbors are all shifted by 1 in the 3D positions
        for s, t in g.edge_set():
            ps, pt = positions[s], positions[t]
            if not ps.is_neighbour(pt):
                raise TQECException(
                    f"The 3D positions of the endpoints of the edge {s}--{t} "
                    f"must be neighbors, but got {ps} and {pt}."
                )
        # 3. Check all the spiders are Z(0) or X(0) or Z(1/2) or Boundary spiders
        for v in g.vertices():
            vt = g.type(v)
            phase = g.phase(v)
            if (vt, phase) not in [
                (zx.VertexType.Z, 0),
                (zx.VertexType.X, 0),
                (zx.VertexType.Z, Fraction(1, 2)),
                (zx.VertexType.BOUNDARY, 0),
            ]:
                raise TQECException(
                    f"Unsupported vertex type and phase: {vt} and {phase}."
                )
            # 4. Check Boundary and Z(1/2) spiders are dangling, additionally
            # Z(1/2) connects to time direction
            if vt == zx.VertexType.BOUNDARY or phase == Fraction(1, 2):
                if g.vertex_degree(v) != 1:
                    raise TQECException(
                        "Boundary or Z(1/2) spider must be dangling, but got "
                        f"{len(g.neighbors(v))} neighbors."
                    )
                if phase == Fraction(1, 2):
                    nb = next(iter(g.neighbors(v)))
                    vp, nbp = positions[v], positions[nb]
                    if abs(nbp.z - vp.z) != 1:
                        raise TQECException(
                            f"Z(1/2) spider must connect to the time direction, "
                            f"but Z(1/2) at {vp} connects to {nbp}."
                        )
        # 5. Check there are no 3D corners
        for v in g.vertices():
            vp = positions[v]
            if len({_get_direction(vp, positions[u]) for u in g.neighbors(v)}) == 3:
                raise TQECException(f"ZX graph has a 3D corner at node {v}.")

    def __getitem__(self, v: int) -> Position3D:
        return self._positions[v]

    @property
    def g(self) -> GraphS:
        """Return the internal ZX graph."""
        return self._g

    @property
    def positions(self) -> dict[int, Position3D]:
        """Return the 3D positions of the vertices."""
        return self._positions

    def get_direction(self, v1: int, v2: int) -> Direction3D:
        """Return the direction connecting two vertices."""
        p1, p2 = self[v1], self[v2]
        return _get_direction(p1, p2)

    @staticmethod
    def from_block_graph(block_graph: BlockGraph) -> PositionedZX:
        """Convert a :py:class:`~tqec.computation.block_graph.BlockGraph` to a
        ZX graph with 3D positions.

        The conversion process is as follows:

        1. For each cube in the block graph, convert it to a ZX vertex.
        2. For each pipe in the block graph, add an edge to the ZX graph with the corresponding endpoints and Hadamard flag.

        Args:
            block_graph: The block graph to be converted to a ZX graph.

        Returns:
            The :py:class:`~tqec.interop.pyzx.positioned_zx.PositionedZX` object converted from the block
            graph.
        """
        v2p: dict[int, Position3D] = {}
        p2v: dict[Position3D, int] = {}
        g = GraphS()

        for cube in block_graph.nodes:
            vt, phase = cube_kind_to_zx(cube.kind)
            v = g.add_vertex(vt, phase=phase)
            v2p[v] = cube.position
            p2v[cube.position] = v

        for edge in block_graph.edges:
            et = zx.EdgeType.HADAMARD if edge.kind.has_hadamard else zx.EdgeType.SIMPLE
            g.add_edge((p2v[edge.u.position], p2v[edge.v.position]), et)

        return PositionedZX(g, v2p)

    def rotate(
        self,
        rotation_axis: Direction3D = Direction3D.Y,
        num_90_degree_rotation: int = 1,
        counterclockwise: bool = True,
    ) -> PositionedZX:
        """Rotate the graph around an axis by ``num_90_degree_rotation * 90`` degrees and
        return a new rotated graph.

        Args:
            rotation_axis: The axis around which to rotate the graph.
            num_90_degree_rotation: The number of 90-degree rotations to apply to the graph.
            counterclockwise: Whether to rotate the graph counterclockwise. If set to False,
                the graph will be rotated clockwise. Defaults to True.

        Returns:
            A graph with positions rotated by the given number of 90-degree rotations.
        """
        n = num_90_degree_rotation % 4

        if n == 0:
            return self

        import numpy as np
        from scipy.spatial.transform import Rotation as R

        def _rotate(p: Position3D) -> Position3D:
            rot_vec = np.array([0, 0, 0])
            axis_idx = rotation_axis.value
            rot_vec[axis_idx] = 1 if axis_idx != 1 else -1
            if not counterclockwise:
                rot_vec *= -1
            rotated = R.from_rotvec(rot_vec * n * np.pi / 2).apply(p.as_tuple())
            return Position3D(*[round_or_fail(i) for i in rotated])

        rotated_positions = {v: _rotate(p) for v, p in self._positions.items()}
        return PositionedZX(self._g, rotated_positions)

    def to_block_graph(self) -> BlockGraph:
        """Convert the positioned ZX graph to a block graph."""
        from tqec.interop.pyzx.synthesis.positioned import positioned_block_synthesis

        return positioned_block_synthesis(self)

    def draw(
        self,
        *,
        figsize: tuple[float, float] = (5, 6),
        title: str | None = None,
        node_size: int = 400,
        hadamard_size: int = 200,
        edge_width: int = 1,
    ) -> tuple[Figure, Axes3D]:
        """Plot the :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` using
        matplotlib.

        Args:
            graph: The ZX graph to plot.
            figsize: The figure size. Default is ``(5, 6)``.
            title: The title of the plot. Default to the name of the graph.
            node_size: The size of the node in the plot. Default is ``400``.
            hadamard_size: The size of the Hadamard square in the plot. Default
                is ``200``.
            edge_width: The width of the edge in the plot. Default is ``1``.

        Returns:
            A tuple of the figure and the axes.
        """
        from tqec.interop.pyzx.plot import plot_positioned_zx_graph

        return plot_positioned_zx_graph(
            self,
            figsize=figsize,
            title=title,
            node_size=node_size,
            hadamard_size=hadamard_size,
            edge_width=edge_width,
        )


def _get_direction(p1: Position3D, p2: Position3D) -> Direction3D:
    """Return the direction connecting two 3D positions."""
    if p1.x != p2.x:
        return Direction3D.X
    if p1.y != p2.y:
        return Direction3D.Y
    return Direction3D.Z
