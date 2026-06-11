from collections.abc import Callable

import pytest
import stim

from tqec.compile.compile import compile_block_graph
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.open_graph import fill_ports_for_minimal_simulation
from tqec.gallery.cnot import cnot
from tqec.gallery.three_cnots import three_cnots


@pytest.mark.parametrize("search_small_area_observables", [True, False])
def test_fill_ports_for_minimal_simulation(search_small_area_observables: bool) -> None:
    graph = cnot()
    filled_graphs = fill_ports_for_minimal_simulation(graph, search_small_area_observables)
    assert len(filled_graphs) == 2
    g1, g2 = filled_graphs
    assert not g1.graph.is_open
    assert not g2.graph.is_open
    assert set(g2.stabilizers) == {"ZIZI", "ZZIZ"}
    assert set(g2.get_external_stabilizers()) == {"ZZII", "ZIZZ"}
    if search_small_area_observables:
        assert set(g1.stabilizers) == {"IXIX", "XIXX"}
        assert set(g1.get_external_stabilizers()) == {"IIXX", "XXIX"}
    else:
        assert set(g1.stabilizers) == {"XXXI", "XIXX"}
        assert set(g1.get_external_stabilizers()) == {"XXXI", "XXIX"}


@pytest.mark.parametrize("graph_factory", [cnot, three_cnots])
def test_fill_ports_is_independent_of_correlation_surface_order(
    graph_factory: Callable[[], BlockGraph],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    find_correlation_surfaces = BlockGraph.find_correlation_surfaces

    def generated_circuits() -> list[tuple[list[str], stim.Circuit]]:
        return [
            (
                filled_graph.stabilizers,
                compile_block_graph(
                    filled_graph.graph,
                    observables=filled_graph.observables,
                ).generate_stim_circuit(
                    1,
                    manhattan_radius=-1,
                    database_path=None,
                ),
            )
            for filled_graph in fill_ports_for_minimal_simulation(graph_factory())
        ]

    expected = generated_circuits()

    def find_reversed_correlation_surfaces(
        self: BlockGraph,
    ) -> list[CorrelationSurface]:
        return list(reversed(find_correlation_surfaces(self)))

    monkeypatch.setattr(
        BlockGraph,
        "find_correlation_surfaces",
        find_reversed_correlation_surfaces,
    )

    assert generated_circuits() == expected
