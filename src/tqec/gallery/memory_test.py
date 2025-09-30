import pytest

from tqec.gallery.memory import memory
from tqec.utils.enums import Basis, PauliBasis


@pytest.mark.parametrize("basis", [Basis.X, Basis.Z, PauliBasis.X, PauliBasis.Z])
def test_xz_memory(basis: Basis | PauliBasis) -> None:
    g = memory(basis)
    assert g.num_cubes == 1
    assert g.num_ports == 0
    assert g.num_pipes == 0


def test_y_memory() -> None:
    g = memory(PauliBasis.Y)
    assert g.num_cubes == 2
    assert g.num_ports == 0
    assert g.num_pipes == 1
