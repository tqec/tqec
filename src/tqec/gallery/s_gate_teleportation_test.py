import pytest
import pyzx as zx

from tqec.gallery.s_gate_teleportation import s_gate_teleportation
from tqec.utils.enums import PauliBasis


def test_s_gate_teleportation_open() -> None:
    g = s_gate_teleportation()
    assert g.num_ports == 2
    assert g.num_cubes == 5
    assert g.spacetime_volume == 2.5
    assert g.num_pipes == 4
    assert len(g.leaf_cubes) == 3
    assert {*g.ports.keys()} == {
        "In",
        "Out",
    }
    assert g.bounding_box_size() == (2, 1, 3)


def test_s_gate_teleportation_open_zx() -> None:
    g = s_gate_teleportation().to_zx_graph().g
    print(g.edge_set())
    g.set_inputs((0,))  # type: ignore
    g.set_outputs((2,))  # type: ignore

    c = zx.qasm("""
qreg q[1];
s q[0];
""")

    assert zx.compare_tensors(c, g)


@pytest.mark.parametrize("in_obs_basis", [PauliBasis.X, PauliBasis.Z, PauliBasis.Y])
def test_move_rotation_filled(in_obs_basis: PauliBasis) -> None:
    g = s_gate_teleportation(in_obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 5
    assert g.num_pipes == 4
    assert len(g.leaf_cubes) == 3


@pytest.mark.parametrize(
    "in_obs_basis, num_surfaces, external_stabilizers",
    [
        (PauliBasis.X, 1, {"XY"}),
        (PauliBasis.Y, 1, {"YX"}),
        (PauliBasis.Z, 1, {"ZZ"}),
    ],
)
def test_s_gate_teleportation_correlation_surface(
    in_obs_basis: PauliBasis, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    io_ports = [0, 2]

    g = s_gate_teleportation(in_obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert {s.external_stabilizer(io_ports) for s in correlation_surfaces} == external_stabilizers


def test_s_gate_teleportation_ports_filling() -> None:
    g = s_gate_teleportation()
    filled_graphs = g.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
