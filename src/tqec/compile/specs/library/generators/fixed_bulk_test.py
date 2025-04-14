import stim

from tqec.compile.specs.library.generators.fixed_bulk import (
    make_fixed_bulk_realignment_plaquette,
)
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis
from tqec.utils.enums import Basis, Orientation


def test_fixed_bulk_realignment_plaquette() -> None:
    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.X,
        z_orientation=Orientation.VERTICAL,
        mq_reset=Basis.X,
        mq_measurement=Basis.Z,
        debug_basis=PauliBasis.X,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RX 4
TICK
CX 4 0
TICK
TICK
CX 4 2
TICK
CX 1 4
TICK
CX 0 4
TICK
MZ 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_basis() == PauliBasis.X

    plaquette = make_fixed_bulk_realignment_plaquette(
        stabilizer_basis=Basis.Z,
        z_orientation=Orientation.HORIZONTAL,
        mq_reset=Basis.Z,
        mq_measurement=Basis.X,
        debug_basis=PauliBasis.Z,
    )
    assert plaquette.qubits == SquarePlaquetteQubits()
    assert len(plaquette.circuit.schedule) == 6
    assert plaquette.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit("""
RZ 4
TICK
CX 0 4
TICK
TICK
CX 2 4
TICK
CX 4 1
TICK
CX 4 0
TICK
MX 4
H 0 1 2 3
""")
    assert plaquette.debug_information.get_basis() == PauliBasis.Z
