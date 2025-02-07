import pytest

from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis


def test_cnot_open() -> None:
    g = cnot()
    assert g.num_ports == 4
    assert g.num_nodes == 10
    assert g.num_edges == 9
    assert len(g.leaf_nodes) == 4
    assert {*g.ports.keys()} == {
        "In_Control",
        "Out_Control",
        "In_Target",
        "Out_Target",
    }


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_cnot_filled(obs_basis: Basis) -> None:
    g = cnot(obs_basis)
    assert g.num_ports == 0
    assert g.num_nodes == 10
    assert g.num_edges == 9
    assert len(g.leaf_nodes) == 4
