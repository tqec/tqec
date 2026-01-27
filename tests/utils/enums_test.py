from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError


def test_zx_basis() -> None:
    assert Basis.Z.flipped() == Basis.X
    assert Basis.X.flipped() == Basis.Z
    assert Basis.X < Basis.Z


def test_pauli_basis_conversion() -> None:
    assert Basis.Z.to_pauli() == Pauli.Z
    assert Basis.X.to_pauli() == Pauli.X
    assert Pauli.Z.to_basis() == Basis.Z
    assert Pauli.X.to_basis() == Basis.X
    for pauli in (Pauli.I, Pauli.Y):
        try:
            pauli.to_basis()
        except TQECError:  # noqa: PERF203
            pass
        else:
            assert False
    assert Pauli.I.to_basis_set() == set()
    assert Pauli.X.to_basis_set() == {Basis.X}
    assert Pauli.Z.to_basis_set() == {Basis.Z}
    assert Pauli.Y.to_basis_set() == {Basis.X, Basis.Z}


def test_pauli() -> None:
    assert Pauli.X.flipped() == Pauli.Z
    assert Pauli.Z.flipped() == Pauli.X
    assert Pauli.Y.flipped() == Pauli.Y
    assert Pauli.I.flipped() == Pauli.I
    assert Pauli.X | Pauli.Z == Pauli.Y
    assert Pauli.Y & Pauli.X == Pauli.X
    assert Pauli.Y & Pauli.Z == Pauli.Z
    assert Pauli.X & Pauli.Z == Pauli.I
    assert Pauli.Y & Pauli.Y == Pauli.Y
    assert list(Pauli.iter_ixzy()) == [Pauli.I, Pauli.X, Pauli.Z, Pauli.Y]
    assert list(Pauli.iter_xzy()) == [Pauli.X, Pauli.Z, Pauli.Y]
    assert list(Pauli.iter_xz()) == [Pauli.X, Pauli.Z]
    assert str(Pauli.I) == "I"
    assert str(Pauli.X) == "X"
    assert str(Pauli.Y) == "Y"
    assert str(Pauli.Z) == "Z"
