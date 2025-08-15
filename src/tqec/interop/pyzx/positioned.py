"""ZX graph with 3D positions."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from pyzx.graph.graph_s import GraphS
from pyzx.utils import EdgeType, VertexType

from tqec.computation.block_graph import BlockGraph
from tqec.interop.pyzx.utils import cube_kind_to_zx
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D


class PositionedZX:
    def __init__(self, g: GraphS, positions: Mapping[int, Position3D]) -> None:
        """Represent a ZX graph with 3D positions and additional constraints.

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
            TQECError: If the constraints are not satisfied.

        """
        self.check_preconditions(g, positions)

        self._g = g
        self._positions: dict[int, Position3D] = dict(positions)

    @staticmethod
    def check_preconditions(g: GraphS, positions: Mapping[int, Position3D]) -> None:
        """Check the preconditions for the ZX graph with 3D positions."""
        # 1. Check the vertex IDs in the graph match the positions
        if g.vertex_set() != set(positions.keys()):
            raise TQECError("The vertex IDs in the ZX graph and the positions do not match.")
        # 2. Check the neighbors are all shifted by 1 in the 3D positions
        for s, t in g.edge_set():
            ps, pt = positions[s], positions[t]
            if not ps.is_neighbour(pt):
                raise TQECError(
                    f"The 3D positions of the endpoints of the edge {s}--{t} "
                    f"must be neighbors, but got {ps} and {pt}."
                )
        # 3. Check all the spiders are Z(0) or X(0) or Z(1/2) or Boundary spiders
        for v in g.vertices():
            vt = g.type(v)
            phase = g.phase(v)
            if (vt, phase) not in [
                (VertexType.Z, 0),
                (VertexType.X, 0),
                (VertexType.Z, Fraction(1, 2)),
                (VertexType.BOUNDARY, 0),
            ]:
                raise TQECError(f"Unsupported vertex type and phase: {vt} and {phase}.")
            # 4. Check Boundary and Z(1/2) spiders are dangling, additionally
            # Z(1/2) connects to time direction
            if vt == VertexType.BOUNDARY or phase == Fraction(1, 2):
                if g.vertex_degree(v) != 1:
                    raise TQECError(
                        "Boundary or Z(1/2) spider must be dangling, but "
                        f"got {len(g.neighbors(v))} neighbors."
                    )
                if phase == Fraction(1, 2):
                    nb = next(iter(g.neighbors(v)))
                    vp, nbp = positions[v], positions[nb]
                    if abs(nbp.z - vp.z) != 1:
                        raise TQECError(
                            "Z(1/2) spider must connect to the time direction, "
                            f"but Z(1/2) at {vp} connects to {nbp}."
                        )
        # 5. Check there are no 3D corners
        for v in g.vertices():
            vp = positions[v]
            if len({_get_direction(vp, positions[u]) for u in g.neighbors(v)}) == 3:
                raise TQECError(f"ZX graph has a 3D corner at node {v}.")

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

    @property
    def p2v(self) -> dict[Position3D, int]:
        """Return the mapping from 3D positions to vertices."""
        return {p: v for v, p in self._positions.items()}

    def get_direction(self, v1: int, v2: int) -> Direction3D:
        """Return the direction connecting two vertices."""
        p1, p2 = self[v1], self[v2]
        return _get_direction(p1, p2)

    @staticmethod
    def from_block_graph(block_graph: BlockGraph) -> PositionedZX:
        """Convert a :py:class:`.BlockGraph` to a ZX graph with 3D positions.

        The conversion process is as follows:

        1. For each cube in the block graph, convert it to a ZX vertex.
        2. For each pipe in the block graph, add an edge to the ZX graph with the corresponding
           endpoints and Hadamard flag.

        Args:
            block_graph: The block graph to be converted to a ZX graph.

        Returns:
            The :py:class:`~tqec.interop.pyzx.positioned_zx.PositionedZX` object converted from
            the block graph.

        """
        v2p: dict[int, Position3D] = {}
        p2v: dict[Position3D, int] = {}
        g = GraphS()

        for cube in sorted(block_graph.cubes, key=lambda c: c.position):
            vt, phase = cube_kind_to_zx(cube.kind)
            v = g.add_vertex(vt, phase=phase)
            v2p[v] = cube.position
            p2v[cube.position] = v

        for edge in block_graph.pipes:
            et = EdgeType.HADAMARD if edge.kind.has_hadamard else EdgeType.SIMPLE
            g.add_edge((p2v[edge.u.position], p2v[edge.v.position]), et)

        return PositionedZX(g, v2p)

    def to_block_graph(self) -> BlockGraph:  # pragma: no cover
        """Convert the positioned ZX graph to a block graph."""
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.interop.pyzx.synthesis.positioned import (  # noqa: PLC0415
            positioned_block_synthesis,
        )

        return positioned_block_synthesis(self)

    def draw(
        self,
        *,
        figsize: tuple[float, float] = (5, 6),
        title: str | None = None,
        node_size: int = 400,
        hadamard_size: int = 200,
        edge_width: int = 1,
    ) -> tuple[Figure, Axes3D]:  # pragma: no cover
        """Plot the :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` using matplotlib.

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
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.interop.pyzx.plot import plot_positioned_zx_graph  # noqa: PLC0415

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
