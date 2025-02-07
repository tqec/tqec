import pytest
import pyzx as zx

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


def test_three_cnots_open_zx() -> None:
    g = three_cnots().to_zx_graph().g
    g.set_inputs((2, 6, 7))
    g.set_outputs((0, 10, 8))

    c = zx.qasm("""
qreg q[3];
cx q[0], q[1];
cx q[1], q[2];
cx q[0], q[2];
""")
    composed = c.to_graph().adjoint() * g
    zx.full_reduce(composed)

    id = zx.qasm("""qreg q[3];""")

    assert zx.compare_tensors(composed, id)


@pytest.mark.parametrize("obs_basis", (Basis.X, Basis.Z))
def test_three_cnots_filled(obs_basis: Basis) -> None:
    g = three_cnots(obs_basis)
    assert g.num_ports == 0
    assert g.num_nodes == 12
    assert g.num_edges == 12
    assert len(g.leaf_nodes) == 6


@pytest.mark.parametrize(
    "obs_basis, num_surfaces, external_stabilizers",
    [
        (Basis.X, 7, {"XXXXII", "IXXIXI", "IIXIIX"}),
        (Basis.Z, 7, {"ZIIZII", "ZZIIZI", "IZZIIZ"}),
    ],
)
def test_three_cnots_correlation_surface(
    obs_basis: Basis, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    io_ports = [2, 6, 7, 0, 10, 8]

    g = three_cnots(obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert external_stabilizers.issubset(
        {s.external_stabilizer(io_ports) for s in correlation_surfaces}
    )
