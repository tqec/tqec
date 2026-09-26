from tqec.compile.detectors.space import GF2Basis, gf2_row_basis


def test_gf2_basis_reduces_and_tracks_rank() -> None:
    basis = GF2Basis()

    assert basis.add(0b1010)
    assert basis.add(0b0110)
    assert not basis.add(0b1100)
    assert basis.rank == 2
    assert basis.contains(0b1100)
    assert basis.reduce(0b1111) == 0b0011


def test_gf2_row_basis_discards_dependent_and_zero_rows() -> None:
    assert len(gf2_row_basis([0, 0b11, 0b101, 0b110])) == 2
