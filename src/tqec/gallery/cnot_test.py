import pytest

import pyzx as zx

from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis


def test_cnot_open() -> None:
    g = cnot()
    assert g.num_ports == 4
    assert g.num_cubes == 10
    assert g.num_pipes == 9
    assert len(g.leaf_cubes) == 4
    assert {*g.ports.keys()} == {
        "In_Control",
        "Out_Control",
        "In_Target",
        "Out_Target",
    }


def test_cnot_open_zx() -> None:
    g = cnot().to_zx_graph().g
    g.set_inputs((0, 7))
    g.set_outputs((3, 9))

    c = zx.qasm("""
qreg q[2];
cx q[0], q[1];
""")
    assert zx.compare_tensors(c, g)


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_cnot_filled(obs_basis: Basis) -> None:
    g = cnot(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 10
    assert g.num_pipes == 9
    assert len(g.leaf_cubes) == 4


@pytest.mark.parametrize(
    "obs_basis, num_surfaces, external_stabilizers",
    [
        (Basis.X, 3, {"XIXX", "XXXI", "IXIX"}),
        (Basis.Z, 3, {"ZIZI", "IZZZ", "ZZIZ"}),
        (None, 6, {"ZIZI", "IZZZ", "ZZIZ", "XIXX", "XXXI", "IXIX"}),
    ],
)
def test_cnot_correlation_surface(
    obs_basis: Basis | None, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    io_ports = [0, 7, 3, 9]

    g = cnot(obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert {
        s.external_stabilizer(io_ports) for s in correlation_surfaces
    } == external_stabilizers
