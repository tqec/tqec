from tqec.circuit.qubit import GridQubit
from tqec.enums import Orientation
from tqec.plaquette.enums import PlaquetteSide
from tqec.plaquette.qubit import SquarePlaquetteQubits


def test_creation() -> None:
    GridQubit(0, 0)
    GridQubit(100000, -2398467235)
    GridQubit(-234897659345, 349578)


def test_square_plaquette_qubits() -> None:
    qubits = SquarePlaquetteQubits()
    top_left = GridQubit(-1, -1)
    top_right = GridQubit(1, -1)
    bot_left = GridQubit(-1, 1)
    bot_right = GridQubit(1, 1)
    center = GridQubit(0, 0)
    assert set(qubits.data_qubits) == {top_left, top_right, bot_left, bot_right}
    assert set(qubits.syndrome_qubits) == {center}
    assert set(qubits.get_qubits_on_side(PlaquetteSide.LEFT)) == {top_left, bot_left}
    assert set(qubits.get_qubits_on_side(PlaquetteSide.RIGHT)) == {top_right, bot_right}
    assert set(qubits.get_qubits_on_side(PlaquetteSide.UP)) == {top_left, top_right}
    assert set(qubits.get_qubits_on_side(PlaquetteSide.DOWN)) == {bot_left, bot_right}
    assert set(qubits.get_edge_qubits(Orientation.HORIZONTAL)) == {
        bot_left,
        bot_right,
    }
    assert set(qubits.get_edge_qubits(Orientation.VERTICAL)) == {
        top_right,
        bot_right,
    }
