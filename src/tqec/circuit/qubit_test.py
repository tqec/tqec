import stim

from tqec.circuit.qubit import GridQubit, count_qubit_accesses, get_used_qubit_indices
from tqec.utils.position import PhysicalQubitPosition2D, Shift2D


def test_grid_qubit_creation() -> None:
    GridQubit(0, 0)
    GridQubit(-1, 10)


def test_grid_qubit_coordinates() -> None:
    assert GridQubit(0, 0).x == 0
    assert GridQubit(0, 0).y == 0
    assert GridQubit(-1, 10).x == -1
    assert GridQubit(-1, 10).y == 10


def test_grid_qubit_operators() -> None:
    q = GridQubit(0, 0)
    assert q + Shift2D(0, 0) == q
    assert q + PhysicalQubitPosition2D(0, 0) == q
    assert q + q == q
    assert q - Shift2D(0, 0) == q
    assert q - PhysicalQubitPosition2D(0, 0) == q
    assert q - q == q
    assert 3 * q == q
    assert q * 3 == q

    assert q + Shift2D(1, 3) == GridQubit(1, 3)
    assert q + PhysicalQubitPosition2D(1, 3) == GridQubit(1, 3)
    assert q + GridQubit(1, 3) == GridQubit(1, 3)

    q = GridQubit(-1, 0)
    assert q + Shift2D(0, 0) == q
    assert q + q == 2 * q
    assert q - q == GridQubit(0, 0)


def test_grid_qubit_in_set() -> None:
    grid_qubits = [GridQubit(i, j) for i in range(10) for j in range(10)]
    assert len(set(grid_qubits)) == len(grid_qubits)
    assert len(set(grid_qubits + grid_qubits)) == len(grid_qubits)

    grid_qubits = [GridQubit(i * (3 + i), 3 * j) for i in range(10) for j in range(10)]
    assert len(set(grid_qubits)) == len(grid_qubits)
    assert len(set(grid_qubits + grid_qubits)) == len(grid_qubits)


def test_grid_qubit_ordering() -> None:
    assert GridQubit(0, 0) < GridQubit(0, 1)
    assert GridQubit(0, 0) < GridQubit(1, 1)
    assert not GridQubit(0, 0) < GridQubit(-1, 1)
    assert not GridQubit(0, 0) < GridQubit(0, -1)


def test_count_qubit_accesses() -> None:
    assert count_qubit_accesses(stim.Circuit("H 0 1 2 3")) == {i: 1 for i in range(4)}
    assert count_qubit_accesses(stim.Circuit("QUBIT_COORDS(0, 0) 0")) == {}
    assert count_qubit_accesses(stim.Circuit("DETECTOR(0) rec[-1]")) == {}
    assert count_qubit_accesses(stim.Circuit("CX rec[-1] 0")) == {0: 1}
    assert count_qubit_accesses(stim.Circuit("H 0 0 1 1 2 2 3 3")) == {i: 2 for i in range(4)}
    assert count_qubit_accesses(stim.Circuit("H 0 1 2 3\nTICK\nH 0 1 2 3")) == {
        i: 2 for i in range(4)
    }
    assert count_qubit_accesses(stim.Circuit("REPEAT 34{\nH 0 1 2 3\nTICK\nH 0 1 2 3\n}")) == {
        i: 34 * 2 for i in range(4)
    }


def test_used_qubit_indices() -> None:
    assert get_used_qubit_indices(stim.Circuit("H 0 1 2 3")) == frozenset(range(4))
    assert get_used_qubit_indices(stim.Circuit("QUBIT_COORDS(0, 0) 0")) == frozenset()
    assert get_used_qubit_indices(stim.Circuit("DETECTOR(0) rec[-1]")) == frozenset()
    assert get_used_qubit_indices(stim.Circuit("CX rec[-1] 0")) == frozenset([0])
    assert get_used_qubit_indices(stim.Circuit("H 0 0 1 1 2 2 3 3")) == frozenset(range(4))
    assert get_used_qubit_indices(stim.Circuit("H 0 1 2 3\nTICK\nH 0 1 2 3")) == frozenset(range(4))
    assert get_used_qubit_indices(
        stim.Circuit("REPEAT 34{\nH 0 1 2 3\nTICK\nH 0 1 2 3\n}")
    ) == frozenset(range(4))


def test_to_qubit_coords_instruction() -> None:
    assert GridQubit(0, 0).to_qubit_coords_instruction(0) == stim.CircuitInstruction(
        "QUBIT_COORDS", [0], [0, 0]
    )
    assert GridQubit(0, 0).to_qubit_coords_instruction(34789) == stim.CircuitInstruction(
        "QUBIT_COORDS", [34789], [0, 0]
    )
    assert GridQubit(-1, 1).to_qubit_coords_instruction(0) == stim.CircuitInstruction(
        "QUBIT_COORDS", [0], [-1, 1]
    )
