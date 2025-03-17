"""Utilities for working with graphs with open ports."""

from dataclasses import dataclass
from functools import reduce
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
    correlation_surfaces = graph.find_correlation_surfaces()
    stabilizers = [s.external_stabilizer_on_graph(graph) for s in correlation_surfaces]
    stabilizer_to_correlation: dict[str, CorrelationSurface] = {
        stabilizer: correlation_surface
        for stabilizer, correlation_surface in zip(stabilizers, correlation_surfaces)
    }
    num_generators = len(stabilizers[0])
    identity = "I" * num_generators
    # powerset of the generators
    for r in range(2, len(stabilizers) + 1):
        for comb in combinations(stabilizers, r):
            stabilizer = reduce(
                _multiply_unsigned_paulis,
                comb,
                identity,
            )
            if stabilizer != identity and stabilizer not in stabilizer_to_correlation:
                correlation_surface = reduce(
                    lambda a, b: a + b,
                    [stabilizer_to_correlation[s] for s in comb],
                )
                stabilizer_to_correlation[stabilizer] = correlation_surface

    stabilizers_ordered_by_area = sorted(
        stabilizer_to_correlation.keys(),
        key=lambda s: stabilizer_to_correlation[s].area(),
    )
    # find a complete set of generators, starting from the smallest area
    generators: list[str] = []
    generators_stim: list[stim.PauliString] = []
    for i, stabilizer in enumerate(stabilizers_ordered_by_area):
        stim_pauli_string = stim.PauliString(stabilizer)
        if i == 0:
            generators.append(stabilizer)
            generators_stim.append(stim_pauli_string)
            continue
        if not _op_is_in_the_group(stim_pauli_string, generators_stim):
            generators.append(stabilizer)
            generators_stim.append(stim_pauli_string)
        if len(generators) == num_generators:
            break

    def is_compatible(s1: str, s2: str) -> bool:
        for i, j in zip(s1, s2):
            if i == "I" or j == "I":
                continue
            if i != j:
                return False
        return True

    # min-clique-cover reduce to graph coloring problem on the complement graph
    nodes = list(range(len(generators)))
    g: nx.Graph[int] = nx.Graph()
    g.add_nodes_from(nodes)
    for i, j in combinations(nodes, 2):
        if not is_compatible(generators[i], generators[j]):
            g.add_edge(i, j)
    coloring = nx.algorithms.coloring.greedy_color(g)
    cliques: dict[int, list[str]] = {}
    for node, color in coloring.items():
        cliques.setdefault(color, []).append(generators[node])

    def ports_basis_for_clique(
        supported_stabilizers: list[str],
    ) -> list[str]:
        port_ops = ["I"] * num_generators
        for s in supported_stabilizers:
            for i, p in enumerate(s):
                port_ops[i] = p
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

        filled_graphs.append(
            FilledGraph(
                graph=fg,
                stabilizers=clique,
                observables=[stabilizer_to_correlation[s] for s in clique],
            )
        )
    return filled_graphs


def _multiply_unsigned_paulis(p1: str, p2: str) -> str:
    from pyzx.pauliweb import multiply_paulis

    return "".join(multiply_paulis(p1[i], p2[i]) for i in range(len(p1)))


def _op_is_in_the_group(
    pauli_string: stim.PauliString,
    basis: list[stim.PauliString],
) -> bool:
    # Decompose into the basis by inverting its tableau.
    tableau = stim.Tableau.from_stabilizers(
        basis,
        allow_redundant=False,
        allow_underconstrained=True,
    )
    inv = tableau.inverse(unsigned=True)
    out_paulis = inv(pauli_string)
    for q in range(len(basis), len(out_paulis)):
        if out_paulis[q] != 0:
            return False
    return True
