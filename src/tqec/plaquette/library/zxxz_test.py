import stim

from tqec.plaquette.enums import PlaquetteOrientation, PlaquetteSide
from tqec.plaquette.library.zxxz import make_zxxz_surface_code_plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.utils.enums import Basis


def test_zxxz_surface_code_memory_plaquette() -> None:
    plaquette = make_zxxz_surface_code_plaquette("X")
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "ZXXZ_basis(X)_VERTICAL"
    assert "H" in plaquette.mergeable_instructions
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("_ZXXZ -> Z____"))
    assert circuit.has_flow(stim.Flow("1 -> _ZXXZ xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
H 0
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 3
TICK
CZ 0 2
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0
TICK
M 0
""")

    plaquette = make_zxxz_surface_code_plaquette("Z")
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "ZXXZ_basis(Z)_VERTICAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("_ZXXZ -> Z____"))
    assert circuit.has_flow(stim.Flow("1 -> _ZXXZ xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
H 0
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 2
TICK
CZ 0 3
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0
TICK
M 0
""")

    plaquette = make_zxxz_surface_code_plaquette("X", x_boundary_orientation="HORIZONTAL")
    assert plaquette.name == "ZXXZ_basis(X)_HORIZONTAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("_XZZX -> Z____"))
    assert circuit.has_flow(stim.Flow("1 -> _XZZX xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
H 0 1 2 3 4
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 2
TICK
CZ 0 3
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 1 2 3 4
TICK
M 0
""")


def test_zxxz_surface_code_init_meas_plaquette() -> None:
    plaquette = make_zxxz_surface_code_plaquette("Z", Basis.Z, Basis.Z)
    assert plaquette.name == "ZXXZ_basis(Z)_VERTICAL_datainit(Z)_datameas(Z)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(
        stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3] xor rec[-4] xor rec[-5]")
    )
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0 1 2 3 4
TICK
H 0 2 3
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 2
TICK
CZ 0 3
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 2 3
TICK
M 0 1 2 3 4
""")
    plaquette = make_zxxz_surface_code_plaquette("X", Basis.X, Basis.X)
    assert plaquette.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(
        stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3] xor rec[-4] xor rec[-5]")
    )
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0 1 2 3 4
TICK
H 0 2 3
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 3
TICK
CZ 0 2
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 2 3
TICK
M 0 1 2 3 4
""")
    plaquette = make_zxxz_surface_code_plaquette(
        "Z",
        Basis.Z,
        Basis.Z,
        x_boundary_orientation="HORIZONTAL",
        init_meas_only_on_side=PlaquetteSide.RIGHT,
    )
    assert plaquette.name == "ZXXZ_basis(Z)_HORIZONTAL_datainit(Z,RIGHT)_datameas(Z,RIGHT)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _Z_X_ xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0 2 4
TICK
H 0 2
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 3
TICK
CZ 0 2
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 2
TICK
M 0 2 4
""")


def test_zxxz_surface_code_projected_plaquette() -> None:
    plaquette = make_zxxz_surface_code_plaquette("X", Basis.X, Basis.X)
    assert plaquette.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)"
    qubits = plaquette.qubits
    plaquette_up = plaquette.project_on_boundary(PlaquetteOrientation.UP)
    assert plaquette_up.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.DOWN),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    assert plaquette_up.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)_UP"
    circuit = plaquette_up.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, 1) 1
QUBIT_COORDS(1, 1) 2
R 0 1 2
TICK
H 0 1
TICK
TICK
H 1 2
TICK
CZ 0 1
TICK
TICK
H 1 2
TICK
CZ 0 2
TICK
H 0 1
TICK
M 0 1 2
""")
    plaquette_down = plaquette.project_on_boundary(PlaquetteOrientation.DOWN)
    assert plaquette_down.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)_DOWN"
    assert plaquette_down.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.UP),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_down.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
R 0 1 2
TICK
H 0 2
TICK
CZ 0 1
TICK
H 1 2
TICK
TICK
CZ 0 2
TICK
H 1 2
TICK
TICK
H 0 2
TICK
M 0 1 2
""")
    plaquette_left = plaquette.project_on_boundary(PlaquetteOrientation.LEFT)
    assert plaquette_left.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)_LEFT"
    assert plaquette_left.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.RIGHT),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_left.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(1, 1) 2
R 0 1 2
TICK
H 0 1
TICK
TICK
H 1 2
TICK
TICK
CZ 0 1
TICK
H 1 2
TICK
CZ 0 2
TICK
H 0 1
TICK
M 0 1 2
""")
    plaquette_right = plaquette.project_on_boundary(PlaquetteOrientation.RIGHT)
    assert plaquette_right.name == "ZXXZ_basis(X)_VERTICAL_datainit(X)_datameas(X)_RIGHT"
    assert plaquette_right.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.LEFT),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_right.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> 1 xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(-1, 1) 2
R 0 1 2
TICK
H 0 2
TICK
CZ 0 1
TICK
H 1 2
TICK
CZ 0 2
TICK
TICK
H 1 2
TICK
TICK
H 0 2
TICK
M 0 1 2
""")


def test_zxxz_surface_code_init_meas_only_on_side() -> None:
    plaquette = make_zxxz_surface_code_plaquette(
        "X", Basis.X, init_meas_only_on_side=PlaquetteSide.RIGHT
    )
    assert plaquette.name == "ZXXZ_basis(X)_VERTICAL_datainit(X,RIGHT)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _ZXXZ xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0 2 4
TICK
H 0 2
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 3
TICK
CZ 0 2
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0
TICK
M 0
""")
    plaquette = make_zxxz_surface_code_plaquette(
        "Z", data_measurement=Basis.Z, init_meas_only_on_side=PlaquetteSide.UP
    )
    assert plaquette.name == "ZXXZ_basis(Z)_VERTICAL_datameas(Z,UP)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> ___XZ xor rec[-1] xor rec[-2] xor rec[-3]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
H 0
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 2
TICK
CZ 0 3
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 2
TICK
M 0 1 2
""")
    plaquette = make_zxxz_surface_code_plaquette(
        "X",
        Basis.X,
        x_boundary_orientation="HORIZONTAL",
        init_meas_only_on_side=PlaquetteSide.LEFT,
    )
    circuit = plaquette.circuit.get_circuit()
    # assert circuit.has_flow(stim.Flow("1 -> _ZXXZ xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0 1 3
TICK
H 0 3
TICK
CZ 0 1
TICK
H 1 2 3 4
TICK
CZ 0 2
TICK
CZ 0 3
TICK
H 1 2 3 4
TICK
CZ 0 4
TICK
H 0 1 2 3 4
TICK
M 0
""")
