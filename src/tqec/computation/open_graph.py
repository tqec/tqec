"""Utilities for working with graphs with open ports."""

from dataclasses import dataclass
from itertools import combinations

import stim
import networkx as nx

from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import YHalfCube, ZXCube
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D


def open_graph_to_stabilizer_tableau(graph: BlockGraph) -> stim.Tableau:
    """When the graph includes no non-Clifford blocks, get the stabilizer tableau
    represented by the graph."""
    if graph.num_ports == 0:
        raise TQECException(
            "The provided graph has no open ports, so no tableau can be generated."
        )
    correlation_surfaces = graph.find_correlation_surfaces()
    external_stabilizers = [
        s.external_stabilizer_on_graph(graph) for s in correlation_surfaces
    ]
    tableau = stim.Tableau.from_stabilizers(
        stabilizers=[stim.PauliString(s) for s in external_stabilizers],
        allow_redundant=True,
    )
    return tableau


@dataclass(frozen=True)
class FilledGraph:
    graph: BlockGraph
    stabilizers: list[str]
    observables: list[CorrelationSurface]


def fill_ports_for_simulation(graph: BlockGraph) -> list[FilledGraph]:
    """Given a block graph with open ports, fill in the ports with the appropriate
    cubes that will minimize the number of simulation runs needed for the complete
    logical observable set.
    """
    if graph.num_ports == 0:
        raise TQECException("The provided graph has no open ports.")
    # Get the stabilizer generators for the graph
    # Here we simply use the canonical stabilizer generators of the stabilizer
    # tableau of the graph. Better generator selection can be made in the future,
    # e.g. using the generators with the smallest correlation surface area.
    tableau = open_graph_to_stabilizer_tableau(graph)
    stabilizers = tableau.to_stabilizers(canonicalize=True)

    def is_compatible(s1: stim.PauliString, s2: stim.PauliString) -> bool:
        for i in s1.pauli_indices():
            if s2[i] not in [0, s1[i]]:
                return False
        return True

    # min-clique-cover reduce to graph coloring problem on the complement graph
    nodes = list(range(len(stabilizers)))
    g: nx.Graph[int] = nx.Graph()
    g.add_nodes_from(nodes)
    for i, j in combinations(nodes, 2):
        if not is_compatible(stabilizers[i], stabilizers[j]):
            g.add_edge(i, j)
    coloring = nx.algorithms.coloring.greedy_color(g)
    cliques: dict[int, list[stim.PauliString]] = {}
    for node, color in coloring.items():
        cliques.setdefault(color, []).append(stabilizers[node])

    def ports_basis_for_clique(
        supported_stabilizers: list[stim.PauliString],
    ) -> list[str]:
        port_ops = ["I"] * len(supported_stabilizers[0])
        for s in supported_stabilizers:
            for i in s.pauli_indices():
                port_ops[i] = "IXYZ"[s[i]]
        # For the ports with operator I, we can choose any basis
        # Here we choose the Z basis for consistency
        return ["Z" if p == "I" else p for p in port_ops]

    filled_graphs = []
    ports = graph.ordered_ports
    for clique in cliques.values():
        fg = graph.clone()
        port_basis = ports_basis_for_clique(clique)
        for port, basis in zip(ports, port_basis):
            port_pos = graph.ports[port]
            if basis == "Y":
                fg.fill_ports({port: YHalfCube()})
                continue
            assert basis in ["Z", "X"]
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

        clique_stabilizers = [str(s)[1:].replace("_", "I") for s in clique]
        correlation_surfaces = fg.find_correlation_surfaces()
        filtered_surfaces = [
            s
            for s in correlation_surfaces
            if s.external_stabilizer_on_graph(graph) in clique_stabilizers
        ]
        assert len(filtered_surfaces) == len(clique_stabilizers)

        filled_graphs.append(
            FilledGraph(
                graph=fg,
                stabilizers=clique_stabilizers,
                observables=filtered_surfaces,
            )
        )
    return filled_graphs
