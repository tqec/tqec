from tqec.compile.detectors.space import GF2Basis, gf2_row_basis, nullspace


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


def test_decomposition_uses_original_independent_generators() -> None:
    basis = GF2Basis([0b1010, 0b1100, 0b0110])
    assert basis.generators == (0b1010, 0b1100)
    assert basis.decompose(0b0110) == 0b11
    assert basis.decompose(0b1010) == 0b01
    assert basis.decompose(0b0001) is None
    assert basis.decompose(0) == 0


def test_nullspace_includes_unused_columns() -> None:
    rows = [0b10101, 0b01101, 0b11000]
    kernel = nullspace(rows, 6)
    assert len(kernel) == 4
    assert GF2Basis(kernel).rank == 4
    assert all((row & vector).bit_count() % 2 == 0 for row in rows for vector in kernel)
    assert nullspace([], 3) == (1, 2, 4)
    assert nullspace([1, 2, 4], 3) == ()
