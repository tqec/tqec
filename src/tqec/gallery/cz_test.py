import pytest

import pyzx as zx

from tqec.utils.exceptions import TQECException
from tqec.gallery.cz import cz
from tqec.utils.position import Position3D


def test_cz_open() -> None:
    g = cz()
    assert g.num_ports == 4
    assert g.num_cubes == 6
    assert g.spacetime_volume == 2
    assert g.num_pipes == 5
    assert len(g.leaf_cubes) == 4
    assert {*g.ports.keys()} == {
        "In_1",
        "Out_1",
        "In_2",
        "Out_2",
    }
    assert g.bounding_box_size() == (2, 3, 3)


def test_cz_open_zx() -> None:
    g = cz().to_zx_graph().g
    g.set_inputs((0, 3))  # type: ignore
    g.set_outputs((2, 5))  # type: ignore

    c = zx.qasm("""
qreg q[2];
cz q[0], q[1];
""")

    assert zx.compare_tensors(c, g)


def test_cz_resolve_ports() -> None:
    port_positions = (
        Position3D(0, 0, 0),
        Position3D(1, -1, 1),
        Position3D(0, 0, 2),
        Position3D(1, 1, 1),
    )
    g = cz("XI -> XZ")
    assert [str(g[pos].kind) for pos in port_positions] == ["XZX", "XZZ", "XZX", "XZZ"]

    g = cz(["XI -> XZ", "IZ -> IZ"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZX", "XZZ", "XZX", "XZZ"]

    g = cz(["ZX -> IX"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZZ", "XXZ", "XZZ", "XXZ"]

    g = cz(["ZZ -> ZZ"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZZ", "XZZ", "XZZ", "XZZ"]

    with pytest.raises(
        TQECException,
        match="Y basis initialization/measurements are not supported yet.",
    ):
        cz("YI -> XZ")

    with pytest.raises(TQECException, match="X_ -> XX is not a valid flow for the CZ gate."):
        cz("XI -> XX")

    with pytest.raises(TQECException, match="Port 0 fails to support both X and Z observable."):
        cz(["XI -> XZ", "ZI -> ZI"])


@pytest.mark.parametrize(
    "flows, num_surfaces, external_stabilizers",
    [
        (["ZZ -> ZZ"], 2, {"ZIZI", "IZIZ"}),
        (["XI -> XZ"], 2, {"IZIZ", "XIXZ"}),
        (None, 4, {"IXZX", "ZIZI", "IZIZ", "XIXZ"}),
    ],
)
def test_cz_correlation_surface(flows: list[str] | None, num_surfaces: int, external_stabilizers: set[str]) -> None:
    io_ports = [0, 3, 2, 5]

    g = cz(flows)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == num_surfaces
    assert {s.external_stabilizer(io_ports) for s in correlation_surfaces} == external_stabilizers


def test_cz_ports_filling() -> None:
    g = cz()
    filled_graphs = g.fill_ports_for_minimal_simulation()
    assert len(filled_graphs) == 2
    assert filled_graphs[0].graph == cz(["XI -> XZ", "IZ -> IZ"])
    assert filled_graphs[1].graph == cz(["ZI -> ZI", "IX -> ZX"])
