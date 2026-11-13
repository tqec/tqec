import pytest

from tqec.gallery.s_gate_teleportation import s_gate_teleportation
from tqec.utils.enums import PauliBasis


def test_s_gate_teleportation_rejects_y_input() -> None:
    with pytest.raises(ValueError, match="X or Z basis"):
        s_gate_teleportation(PauliBasis.Y)


@pytest.mark.parametrize("basis", [PauliBasis.X, PauliBasis.Z, None])
def test_s_gate_teleportation_ports(basis: PauliBasis | None) -> None:
    g = s_gate_teleportation(basis)
    assert g.num_ports == (2 if basis is None else 0)
