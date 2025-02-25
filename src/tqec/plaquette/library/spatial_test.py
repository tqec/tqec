import stim

from tqec.utils.enums import Basis
from tqec.plaquette.library.spatial import make_spatial_cube_arm_plaquette
from tqec.plaquette.qubit import SquarePlaquetteQubits


def test_spatial_cube_arm_plaquette() -> None:
    plaquette = make_spatial_cube_arm_plaquette(Basis.X, "UP", is_reverse=False)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_X_UP"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
RZ 3
TICK
CX 0 3
TICK
CX 0 1
TICK
TICK
CX 0 2
TICK
CX 3 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.X, "UP", is_reverse=True)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_X_UP_REVERSE"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
RZ 3
TICK
CX 0 3
TICK
CX 0 2
TICK
TICK
CX 0 1
TICK
CX 3 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.X, "DOWN", is_reverse=False)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_X_DOWN"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RZ 1
TICK
RZ 0
TICK
CX 1 0
TICK
CX 0 3
TICK
TICK
CX 0 4
TICK
CX 0 1
TICK
MX 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.X, "DOWN", is_reverse=True)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_X_DOWN_REVERSE"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RZ 1
TICK
RZ 0
TICK
CX 1 0
TICK
CX 0 4
TICK
TICK
CX 0 3
TICK
CX 0 1
TICK
MX 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.Z, "UP", is_reverse=False)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_Z_UP"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
RZ 3
TICK
CX 0 3
TICK
CZ 0 1
TICK
TICK
CZ 0 2
TICK
CX 3 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.Z, "UP", is_reverse=True)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_Z_UP_REVERSE"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
RZ 3
TICK
CX 0 3
TICK
CZ 0 2
TICK
TICK
CZ 0 1
TICK
CX 3 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.Z, "DOWN", is_reverse=False)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_Z_DOWN"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RZ 1
TICK
RZ 0
TICK
CX 1 0
TICK
CZ 0 3
TICK
TICK
CZ 0 4
TICK
CX 0 1
TICK
MX 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(Basis.Z, "DOWN", is_reverse=True)
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_Z_DOWN_REVERSE"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RZ 1
TICK
RZ 0
TICK
CX 1 0
TICK
CZ 0 4
TICK
TICK
CZ 0 3
TICK
CX 0 1
TICK
MX 0
"""
    )
    plaquette = make_spatial_cube_arm_plaquette(
        Basis.X, "UP", is_reverse=False, is_corner_trimmed=True
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert plaquette.name == "SPATIAL_CUBE_ARM_X_UP_CORNER_TRIMMED"
    circuit = plaquette.circuit.get_circuit()
    assert circuit == stim.Circuit(
        """
QUBIT_COORDS(0, 0) 0
QUBIT_COORDS(-1, -1) 1
QUBIT_COORDS(1, -1) 2
QUBIT_COORDS(-1, 1) 3
QUBIT_COORDS(1, 1) 4
RX 0
RZ 3
TICK
CX 0 3
TICK
TICK
TICK
TICK
CX 0 2
TICK
CX 3 0
"""
    )
