import pytest

from tqec.gallery.cz import cz
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


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
        TQECError,
        match=r"Y basis initialization/measurements are not supported yet.",
    ):
        cz("YI -> XZ")

    with pytest.raises(TQECError, match=r"X_ -> XX is not a valid flow for the CZ gate."):
        cz("XI -> XX")

    with pytest.raises(TQECError, match=r"Port 0 fails to support both X and Z observable."):
        cz(["XI -> XZ", "ZI -> ZI"])
