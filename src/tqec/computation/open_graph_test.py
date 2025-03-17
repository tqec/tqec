import stim

from tqec.computation.open_graph import open_graph_to_stabilizer_tableau
from tqec.gallery.cnot import cnot


def test_open_graph_to_stabilizer_tableau() -> None:
    graph = cnot()
    print(graph.ordered_ports)
    tableau = open_graph_to_stabilizer_tableau(graph)
    # In_Control, In_Target, Out_Control, Out_Target
    assert tableau.to_stabilizers(canonicalize=True) == [
        stim.PauliString("+X_XX"),
        stim.PauliString("+Z_Z_"),
        stim.PauliString("+_X_X"),
        stim.PauliString("+_ZZZ"),
    ]
