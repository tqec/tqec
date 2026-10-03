import pytest
import pyzx as zx

from tqec.gallery.s import s
from tqec.utils.enums import Basis


def test_s_open() -> None:
    g = s()
    assert g.num_ports == 2
    assert g.num_cubes == 5
    assert g.spacetime_volume == 2.5
    assert g.num_pipes == 4
    assert len(g.leaf_cubes) == 3
    assert {*g.ports.keys()} == {"In", "Out"}
    assert g.bounding_box_size() == (2, 1, 3)


def test_s_open_zx() -> None:
    g = s().to_zx_graph().g
    g.set_inputs((0,))
    g.set_outputs((2,))

    c = zx.qasm("""
qreg q[1];
s q[0];
""")
    assert zx.compare_tensors(c, g)


@pytest.mark.parametrize("obs_basis", [Basis.Z, Basis.X])
def test_s_filled(obs_basis: Basis) -> None:
    g = s(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 5
    assert g.num_pipes == 4
    assert len(g.leaf_cubes) == 3


@pytest.mark.parametrize(
    "obs_basis, num_surfaces",
    [
        (None, 2),
        (Basis.Z, 1),
        (Basis.X, 1),
    ],
)
def test_s_correlation_surface(obs_basis: Basis | None, num_surfaces: int) -> None:
    g = s(obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
