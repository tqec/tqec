import pytest

from tqec.gallery.s_gate_teleportation import s_gate_teleportation
from tqec.utils.enums import PauliBasis
from tqec.utils.position import Position3D


def test_s_gate_teleportation_rejects_y_input() -> None:
    with pytest.raises(ValueError, match="X or Z basis"):
        s_gate_teleportation(PauliBasis.Y)


@pytest.mark.parametrize("basis", [PauliBasis.X, PauliBasis.Z, None])
def test_s_gate_teleportation_ports(basis: PauliBasis | None) -> None:
    g = s_gate_teleportation(basis)
    assert g.num_ports == (2 if basis is None else 0)


@pytest.mark.parametrize(
    ("basis", "in_kind", "out_kind"),
    [(PauliBasis.X, "XZX", "Y"), (PauliBasis.Z, "XZZ", "XZZ")],
    ids=["x_to_y", "z_to_z"],
)
def test_s_gate_teleportation_port_kinds(basis: PauliBasis, in_kind: str, out_kind: str) -> None:
    g = s_gate_teleportation(basis)
    in_position, out_position = Position3D(0, 0, 0), Position3D(0, 0, 2)
    assert [str(g[pos].kind) for pos in (in_position, out_position)] == [in_kind, out_kind]
