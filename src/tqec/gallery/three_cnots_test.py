import pytest

from tqec.gallery.three_cnots import three_cnots
from tqec.utils.enums import Basis


def test_three_cnots_OPEN() -> None:
    g = three_cnots()
    assert g.num_ports == 6
    assert g.num_nodes == 12
    assert g.num_edges == 12
    assert len(g.leaf_nodes) == 6
    assert {*g.ports.keys()} == {
        "In_a",
        "Out_a",
        "In_b",
        "Out_b",
        "In_c",
        "Out_c",
    }


@pytest.mark.parametrize("obs_basis", (Basis.X, Basis.Z))
def test_three_cnots_filled(obs_basis: Basis) -> None:
    g = three_cnots(obs_basis)
    assert g.num_ports == 0
    assert g.num_nodes == 12
    assert g.num_edges == 12
    assert len(g.leaf_nodes) == 6
