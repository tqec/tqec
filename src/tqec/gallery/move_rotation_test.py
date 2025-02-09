import pytest
import pyzx as zx

from tqec.gallery.move_rotation import move_rotation
from tqec.utils.enums import Basis


def test_move_rotation_open() -> None:
    g = move_rotation()
    assert g.num_ports == 2
    assert g.num_nodes == 5
    assert g.num_edges == 4
    assert len(g.leaf_nodes) == 2
    assert {*g.ports.keys()} == {
        "In",
        "Out",
    }


def test_move_rotation_open_zx() -> None:
    g = move_rotation().to_zx_graph().g
    g.set_inputs((0,))  # type: ignore
    g.set_outputs((4,))  # type: ignore

    c = zx.qasm("""qreg q[1];""")

    assert zx.compare_tensors(c, g)


@pytest.mark.parametrize("obs_basis", [Basis.X, Basis.Z])
def test_move_rotation_filled(obs_basis: Basis) -> None:
    g = move_rotation(obs_basis)
    assert g.num_ports == 0
    assert g.num_nodes == 5
    assert g.num_edges == 4
    assert len(g.leaf_nodes) == 2


@pytest.mark.parametrize(
    "obs_basis, num_surfaces, external_stabilizers",
    [
        (Basis.X, 1, {"XX"}),
        (Basis.Z, 1, {"ZZ"}),
        (None, 2, {"XX", "ZZ"}),
    ],
)
def test_move_rotation_correlation_surface(
    obs_basis: Basis | None, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    io_ports = [0, 4]

    g = move_rotation(obs_basis)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert {
        s.external_stabilizer(io_ports) for s in correlation_surfaces
    } == external_stabilizers
