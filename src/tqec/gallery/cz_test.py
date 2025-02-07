import pytest

from tqec.utils.exceptions import TQECException
from tqec.gallery.cz import cz
from tqec.utils.position import Position3D


def test_cz_open() -> None:
    g = cz()
    assert g.num_ports == 4
    assert g.num_nodes == 6
    assert g.num_edges == 5
    assert len(g.leaf_nodes) == 4
    assert {*g.ports.keys()} == {
        "In_1",
        "Out_1",
        "In_2",
        "Out_2",
    }


def test_cz_resolve_ports() -> None:
    port_positions = (
        Position3D(0, 0, 0),
        Position3D(1, -1, 1),
        Position3D(0, 0, 2),
        Position3D(1, 1, 1),
    )
    g = cz("XI -> XZ")
    assert [str(g[pos].kind) for pos in port_positions] == ["XZX", "XZX", "XZZ", "XZZ"]

    g = cz(["XI -> XZ", "IZ -> IZ"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZX", "XZX", "XZZ", "XZZ"]

    g = cz(["ZX -> IX"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZZ", "XZZ", "XXZ", "XXZ"]

    g = cz(["ZZ -> ZZ"])
    assert [str(g[pos].kind) for pos in port_positions] == ["XZZ", "XZZ", "XZZ", "XZZ"]

    with pytest.raises(
        TQECException,
        match="Y basis initialization/measurements are not supported yet.",
    ):
        cz("YI -> XZ")

    with pytest.raises(
        TQECException, match="X_ -> XX is not a valid flow for the CZ gate."
    ):
        cz("XI -> XX")

    with pytest.raises(
        TQECException, match="Port 0 fails to support both X and Z observable."
    ):
        cz(["XI -> XZ", "ZI -> ZI"])
