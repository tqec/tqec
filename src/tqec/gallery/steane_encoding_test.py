import pytest

from tqec.gallery.steane_encoding import steane_encoding
from tqec.utils.enums import Basis


def test_steane_encoding_OPEN() -> None:
    g = steane_encoding()
    assert g.num_ports == 7
    assert g.num_cubes == 19
    assert g.spacetime_volume == 12
    assert g.num_pipes == 20
    assert len(g.leaf_cubes) == 7
    assert g.bounding_box_size() == (4, 3, 4)


@pytest.mark.parametrize("obs_basis", (Basis.X, Basis.Z))
def test_steane_encoding_filled(obs_basis: Basis) -> None:
    g = steane_encoding(obs_basis)
    assert g.num_ports == 0
    assert g.num_cubes == 19
    assert g.num_pipes == 20
    assert len(g.leaf_cubes) == 7


@pytest.mark.parametrize(
    "obs_basis, num_surfaces, external_stabilizers",
    [
        (Basis.X, 3, {"IXXIIXX", "IXIXXXI", "XIIXIXX"}),
        (Basis.Z, 4, {"ZZIIIZI", "IZZIZII", "ZIIZZII", "ZIZIIIZ"}),
    ],
)
def test_steane_encoding_correlation_surface(
    obs_basis: Basis, num_surfaces: int, external_stabilizers: set[str]
) -> None:
    g = steane_encoding(obs_basis)
    io_ports = [18, 12, 17, 4, 7, 9, 14]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert external_stabilizers == {s.external_stabilizer(io_ports) for s in correlation_surfaces}


def test_steane_encoding_ports_filling() -> None:
    g = steane_encoding()
    filled_graphs = g.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
    assert set(filled_graphs[0].stabilizers) == {"IXXIIXX", "IXIXXXI", "XIIXIXX"}
    assert set(filled_graphs[1].stabilizers) == {
        "ZZIIIZI",
        "IZZIZII",
        "ZIIZZII",
        "ZIZIIIZ",
    }
