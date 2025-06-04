import pytest

import pyzx as zx

from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis


def test_cnot_open() -> None:
    g = cnot()
    assert g.num_ports == 4
    assert g.num_cubes == 10
    assert g.spacetime_volume == 6
    assert g.num_pipes == 9
    assert len(g.leaf_cubes) == 4
    assert {*g.ports.keys()} == {
        "In_Control",
        "Out_Control",
        "In_Target",
        "Out_Target",
    }
    assert g.bounding_box_size() == (2, 2, 4)


def test_cnot_open_zx() -> None:
    g = cnot().to_zx_graph().g
    g.set_inputs((0, 6))  # type: ignore
    g.set_outputs((3, 9))  # type: ignore

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
        (Basis.X, 2, {"XIXX", "IXIX"}),
        (Basis.Z, 2, {"ZIZI", "ZZIZ"}),
        (None, 4, {"ZIZI", "ZZIZ", "XIXX", "IXIX"}),
    ],
)
def test_cnot_correlation_surface(obs_basis: Basis | None, num_surfaces: int, external_stabilizers: set[str]) -> None:
    g = cnot(obs_basis)
    io_ports = [0, 6, 3, 9]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert {s.external_stabilizer(io_ports) for s in correlation_surfaces} == external_stabilizers


def test_compose_two_cnots() -> None:
    g1 = cnot()
    g2 = cnot()
    g_composed = g1.compose(g2, "Out_Control", "In_Control")
    assert g_composed.num_cubes == 18
    assert g_composed.num_ports == 4


def test_cnot_ports_filling() -> None:
    g = cnot()
    filled_graphs = g.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
    assert set(filled_graphs[0].stabilizers) == {"XIXX", "IXIX"}
    assert set(filled_graphs[1].stabilizers) == {"ZIZI", "ZZIZ"}
