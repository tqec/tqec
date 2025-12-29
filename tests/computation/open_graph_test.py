import pytest

from tqec.computation.open_graph import fill_ports_for_minimal_simulation
from tqec.gallery.cnot import cnot


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
