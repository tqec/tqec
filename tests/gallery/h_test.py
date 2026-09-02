import pytest
import pyzx as zx

from tqec.gallery.h import h
from tqec.utils.enums import Basis


def test_h_open() -> None:
    g = h()
    assert g.num_ports == 2
    assert g.num_cubes == 4
    assert g.spacetime_volume == 2
    assert g.num_pipes == 3
    assert len(g.leaf_cubes) == 2
    assert {*g.ports.keys()} == {"In", "Out"}
    assert g.bounding_box_size() == (1, 1, 4)


def test_h_open_zx() -> None:
    g = h().to_zx_graph().g
    g.set_inputs((0,))
    g.set_outputs((3,))

    c = zx.qasm("""
qreg q[1];
h q[0];
""")
    assert zx.compare_tensors(c, g)


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_h_filled(obs_basis: Basis) -> None:
    g = h(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 4
    assert g.num_pipes == 3
    assert len(g.leaf_cubes) == 2


@pytest.mark.parametrize(
    "obs_basis, num_surfaces",
    [
        (None, 2),
        (Basis.X, 1),
        (Basis.Z, 1),
    ],
)
def test_h_correlation_surface(obs_basis: Basis | None, num_surfaces: int) -> None:
    g = h(obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
