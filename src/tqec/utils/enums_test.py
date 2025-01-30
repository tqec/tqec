from tqec.utils.enums import Basis


def test_zx_basis() -> None:
    assert Basis.Z.flipped() == Basis.X
    assert Basis.X.flipped() == Basis.Z
