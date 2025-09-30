"""Utilities for working with graphs with open ports."""

import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from functools import reduce
from itertools import combinations
from typing import Final

import networkx as nx
from pyzx.pauliweb import multiply_paulis

from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import YHalfCube, ZXCube
from tqec.interop.pyzx.correlation import reduce_observables_to_minimal_generators
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError, TQECWarning
from tqec.utils.position import Direction3D


@dataclass(frozen=True)
class FilledGraph:
    """A block graph without open ports that can be used for simulation.

    Attributes:
        graph: The block graph with all ports filled.
        stabilizers: The external stabilizers simulable on the filled graph.
        observables: The correlation surfaces that can be used as logical observables
            for the simulation. A list of independent correlation surfaces with the
            area as small as possible is chosen.

    """

    graph: BlockGraph
    stabilizers: list[str]
    observables: list[CorrelationSurface]

    def __post_init__(self) -> None:
        if self.graph.num_ports != 0:
            raise TQECError("The filled graph should not have open ports.")
        if len(self.stabilizers) != len(self.observables):
            raise TQECError("The number of stabilizers and observables should match.")

    def get_external_stabilizers(self) -> list[str]:
        """Return the external stabilizers of the correlation surfaces."""
        return [obs.external_stabilizer_on_graph(self.graph) for obs in self.observables]


def fill_ports_for_minimal_simulation(
    graph: BlockGraph,
    search_small_area_observables: bool = False,
) -> list[FilledGraph]:
    """Fill the ports of the provided ``graph`` to minimize the number of simulation runs.

    Given a block graph with open ports, fill in the ports with the appropriate cubes that will
    minimize the number of simulation runs needed for the complete logical observable set.

    The key idea is that stabilizers within the same clique should have compatible
    Paulis at their ports. This allows a single simulation run to simultaneously
    simulate for all stabilizers in a clique. Minimizing the number of simulations,
    therefore, translates to minimizing the number of cliques while ensuring full
    coverage of all stabilizers. This leads to solving the minimum clique cover
    problem on a graph, which in turn reduces to a graph coloring problem on its
    complement.

    Args:
        graph: The block graph with open ports.
        search_small_area_observables: If True, the algorithm will try to construct
            all the possible correlation surfaces that can be used as logical
            observables and select the generators with the smallest area. This will
            result in constructing exponentially many correlation surfaces, which
            can be slow for graphs with large number of ports.

    Returns:
        A list of :class:`~tqec.computation.open_graph.FilledGraph` instances, each
        containing a block graph with all ports filled and a set of correlation
        surfaces that can be used as logical observables for the simulation on that
        block graph.

    """
    num_ports = graph.num_ports
    if num_ports == 0:
        raise TQECError("The provided graph has no open ports.")
    # heuristic threshold for large number of ports
    _heuristic_threshold: Final[int] = 16
    if search_small_area_observables and num_ports > _heuristic_threshold:
        warnings.warn(
            "The algorithm will construct all exponentially many correlation "
            "surfaces, which can be slow for graphs with large number of ports. "
            "Consider setting `search_small_area_observables=False` for better "
            "performance.",
            TQECWarning,
        )

    correlation_surfaces = graph.find_correlation_surfaces(reduce_to_minimal_generators=True)
    stab_to_surface: dict[str, CorrelationSurface] = {
        s.external_stabilizer_on_graph(graph): s for s in correlation_surfaces
    }
    generators = list(stab_to_surface.keys())

    if search_small_area_observables:
        identity = "I" * num_ports
        # Need to collect all the possible correlation surfaces because we want
        # to find the generators with the smallest correlation surface area
        for stabilizer, comb in _iter_stabilizer_group(generators):
            if stabilizer != identity and stabilizer not in stab_to_surface:
                correlation_surface = reduce(
                    lambda a, b: a ^ b,
                    [stab_to_surface[s] for s in comb],
                )
                stab_to_surface[stabilizer] = correlation_surface
        generators = list(
            reduce_observables_to_minimal_generators(stab_to_surface, num_ports).keys()
        )

    # Two stabilizers are compatible if they can agree on the supported observable
    # basis on the common ports. We can construct a graph that assigns a node to
    # each stabilizer and an edge between two nodes if the stabilizers are compatible.
    # Then we can solve the minimum clique cover problem to find the minimum
    # number of cliques that cover all the nodes in the graph. Each clique will
    # correspond to a port configuration that can be used for simulation.
    # Here we solve the graph coloring problem on the complement graph, which is
    # equivalent to the clique cover problem on the original graph.
    nodes = list(range(len(generators)))
    g: nx.Graph[int] = nx.Graph()
    g.add_nodes_from(nodes)
    for i, j in combinations(nodes, 2):
        if not _is_compatible_paulis(generators[i], generators[j]):
            g.add_edge(i, j)
    # Solve with heuristic greedy coloring
    coloring = nx.algorithms.coloring.greedy_color(g)
    cliques: dict[int, list[str]] = {}
    for node, color in coloring.items():
        cliques.setdefault(color, []).append(generators[node])

    def ports_basis_for_clique(
        supported_stabilizers: list[str],
    ) -> list[str]:
        port_ops = ["I"] * num_ports
        for s in supported_stabilizers:
            for i, p in enumerate(s):
                if p != "I":
                    port_ops[i] = p
        # For the ports with operator I, we can choose any basis
        # Here we choose the Z basis for consistency
        return ["Z" if p == "I" else p for p in port_ops]

    # Fill in the ports and create the filled graphs
    ports = graph.ordered_ports
    filled_graphs: list[FilledGraph] = []
    for clique in cliques.values():
        fg = graph.clone()
        port_basis = ports_basis_for_clique(clique)
        for port, basis in zip(ports, port_basis):
            port_pos = graph.ports[port]
            if basis == "Y":  # pragma: no cover
                fg.fill_ports({port: YHalfCube()})
                continue
            assert basis in ["Z", "X"]
            # Match the basis of the pipe at the port
            pipe_at_port = graph.pipes_at(port_pos)[0]
            pipe_kind = pipe_at_port.kind
            at_head = pipe_at_port.u == graph[port_pos]
            fill_kind = ZXCube(
                *[
                    pipe_kind.get_basis_along(dir, at_head) or Basis(basis)
                    for dir in Direction3D.all_directions()
                ]
            )
            fg.fill_ports({port: fill_kind})
        assert fg.num_ports == 0

        filled_graphs.append(
            FilledGraph(
                graph=fg,
                stabilizers=clique,
                observables=[stab_to_surface[s] for s in clique],
            )
        )
    return filled_graphs


def _multiply_unsigned_paulis(p1: str, p2: str) -> str:
    return "".join(
        multiply_paulis(
            p1[i],
            p2[i],
        )
        for i in range(len(p1))
    )


def _iter_stabilizer_group(
    generators: list[str],
) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Iterate over the stabilizer group generated by the given generators.

    Return the stabilizer and the generators that generate it.

    """
    identity = "I" * len(generators[0])
    # powerset of the generators
    for r in range(1, len(generators) + 1):
        for comb in combinations(generators, r):
            output = identity
            for gen in comb:
                output = _multiply_unsigned_paulis(output, gen)

            yield (output, comb)


def _is_compatible_paulis(s1: str, s2: str) -> bool:
    for i, j in zip(s1, s2):
        if i == "I" or j == "I":
            continue
        if i != j:
            return False
    return True
