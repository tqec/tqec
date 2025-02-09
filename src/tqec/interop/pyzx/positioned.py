"""ZX graph with 3D positions."""

from fractions import Fraction
from typing import Mapping

import pyzx as zx
from pyzx.graph.graph_s import GraphS

from tqec.interop.pyzx.utils import is_boundary
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, Position3D


class PositionedZX:
    def __init__(self, g: GraphS, positions: Mapping[int, Position3D]) -> None:
        """A ZX graph with 3D positions and additional constraints.

        The constraints are:

        0. All the Boundary vertices are labeled as inputs or outputs.
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
        # 0. Check all the Boundary vertices are labeled as inputs or outputs
        iset, oset = set(g.inputs()), set(g.outputs())
        boundaries = {v for v in g.vertices() if is_boundary(g, v)}
        if len(iset) != len(g.inputs()) or len(oset) != len(g.outputs()):
            raise TQECException("Duplicate vertices are labeled as inputs or outputs.")
        if boundaries != iset | oset:
            raise TQECException(
                "Inputs + Outputs must be equal to all the boundary vertices."
            )
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


def _get_direction(p1: Position3D, p2: Position3D) -> Direction3D:
    """Return the direction connecting two 3D positions."""
    if p1.x != p2.x:
        return Direction3D.X
    if p1.y != p2.y:
        return Direction3D.Y
    return Direction3D.Z
