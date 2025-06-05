import stim

from tqec.plaquette.enums import PlaquetteOrientation, PlaquetteSide
from tqec.plaquette.library.css import make_css_surface_code_plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.utils.enums import Basis


def test_css_surface_code_memory_plaquette() -> None:
    plaquette = make_css_surface_code_plaquette("X")
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "CSS_basis(X)_VERTICAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XXXX xor rec[-1]"))
    assert circuit.has_flow(stim.Flow("_XXXX -> 1 xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
TICK
CX 0 1
TICK
CX 0 3
TICK
CX 0 2
TICK
CX 0 4
TICK
MX 0
""")
    plaquette = make_css_surface_code_plaquette("Z")
    assert plaquette.name == "CSS_basis(Z)_VERTICAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _ZZZZ xor rec[-1]"))
    assert circuit.has_flow(stim.Flow("_ZZZZ -> 1 xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
CX 1 0
TICK
CX 2 0
TICK
CX 3 0
TICK
CX 4 0
TICK
M 0
""")
    plaquette = make_css_surface_code_plaquette("X", x_boundary_orientation="HORIZONTAL")
    assert plaquette.name == "CSS_basis(X)_HORIZONTAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XXXX xor rec[-1]"))
    assert circuit.has_flow(stim.Flow("_XXXX -> 1 xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
TICK
CX 0 1
TICK
CX 0 2
TICK
CX 0 3
TICK
CX 0 4
TICK
MX 0
""")
    plaquette = make_css_surface_code_plaquette("Z", x_boundary_orientation="HORIZONTAL")
    assert plaquette.name == "CSS_basis(Z)_HORIZONTAL"
    circuit = plaquette.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _ZZZZ xor rec[-1]"))
    assert circuit.has_flow(stim.Flow("_ZZZZ -> 1 xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
CX 1 0
TICK
CX 3 0
TICK
CX 2 0
TICK
CX 4 0
TICK
M 0
""")


def test_css_surface_code_init_meas_plaquette() -> None:
    plaquette = make_css_surface_code_plaquette("Z", Basis.Z, Basis.Z)
    assert plaquette.name == "CSS_basis(Z)_VERTICAL_datainit(Z)_datameas(Z)"
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
CX 1 0
TICK
CX 2 0
TICK
CX 3 0
TICK
CX 4 0
TICK
M 0 1 2 3 4
""")
    plaquette = make_css_surface_code_plaquette("X", Basis.X, Basis.X)
    assert plaquette.name == "CSS_basis(X)_VERTICAL_datainit(X)_datameas(X)"
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
RX 0 1 2 3 4
TICK
CX 0 1
TICK
CX 0 3
TICK
CX 0 2
TICK
CX 0 4
TICK
MX 0 1 2 3 4
""")


def test_css_surface_code_projected_plaquette() -> None:
    plaquette = make_css_surface_code_plaquette("X")
    assert plaquette.name == "CSS_basis(X)_VERTICAL"
    qubits = plaquette.qubits
    plaquette_up = plaquette.project_on_boundary(PlaquetteOrientation.UP)
    assert plaquette_up.name == "CSS_basis(X)_VERTICAL_UP"
    assert plaquette_up.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.DOWN),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_up.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XX xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, 1) 1
QUBIT_COORDS(1, 1) 2
RX 0
TICK
TICK
CX 0 1
TICK
TICK
CX 0 2
TICK
MX 0
""")
    plaquette_down = plaquette.project_on_boundary(PlaquetteOrientation.DOWN)
    assert plaquette_down.name == "CSS_basis(X)_VERTICAL_DOWN"
    assert plaquette_down.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.UP),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_down.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XX xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
RX 0
TICK
CX 0 1
TICK
TICK
CX 0 2
TICK
TICK
MX 0
""")
    plaquette_left = plaquette.project_on_boundary(PlaquetteOrientation.LEFT)
    assert plaquette_left.name == "CSS_basis(X)_VERTICAL_LEFT"
    assert plaquette_left.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.RIGHT),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_left.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XX xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(1, -1) 1
QUBIT_COORDS(1, 1) 2
RX 0
TICK
TICK
TICK
CX 0 1
TICK
CX 0 2
TICK
MX 0
""")
    plaquette_right = plaquette.project_on_boundary(PlaquetteOrientation.RIGHT)
    assert plaquette_right.name == "CSS_basis(X)_VERTICAL_RIGHT"
    assert plaquette_right.qubits == PlaquetteQubits(
        data_qubits=qubits.get_qubits_on_side(PlaquetteSide.LEFT),
        syndrome_qubits=qubits.syndrome_qubits,
    )
    circuit = plaquette_right.circuit.get_circuit()
    assert circuit.has_flow(stim.Flow("1 -> _XX xor rec[-1]"))
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(-1, 1) 2
RX 0
TICK
CX 0 1
TICK
CX 0 2
TICK
TICK
TICK
MX 0
""")


def test_css_surface_code_init_meas_only() -> None:
    plaquette = make_css_surface_code_plaquette(
        "X", data_initialization=Basis.X, init_meas_only_on_side=PlaquetteSide.RIGHT
    )
    assert plaquette.name == "CSS_basis(X)_VERTICAL_datainit(X,RIGHT)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0 2 4
TICK
CX 0 1
TICK
CX 0 3
TICK
CX 0 2
TICK
CX 0 4
TICK
MX 0
""")
    plaquette = make_css_surface_code_plaquette(
        "Z", data_measurement=Basis.Z, init_meas_only_on_side=PlaquetteSide.UP
    )
    assert plaquette.name == "CSS_basis(Z)_VERTICAL_datameas(Z,UP)"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit("""
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
R 0
TICK
CX 1 0
TICK
CX 2 0
TICK
CX 3 0
TICK
CX 4 0
TICK
M 0 1 2
""")
