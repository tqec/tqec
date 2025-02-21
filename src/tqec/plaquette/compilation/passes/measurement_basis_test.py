import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.utils.enums import Basis
from tqec.plaquette.compilation.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)


def _s(circuit: str) -> ScheduledCircuit:
    """Small helper to reduce clutter of long names."""
    return ScheduledCircuit.from_circuit(stim.Circuit(circuit))


def test_compilation_pass_creation() -> None:
    ChangeMeasurementBasisPass(Basis.X)
    ChangeMeasurementBasisPass(Basis.Z)


def test_simple_measurement_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(Basis.Z)
    assert compilation_pass.run(_s("M 0")) == _s("M 0")
    assert compilation_pass.run(_s("MZ 0")) == _s("MZ 0")
    assert compilation_pass.run(_s("M 12")) == _s("M 12")
    assert compilation_pass.run(_s("TICK\nMX 0")) == _s("H 0\nTICK\nMZ 0")
    assert compilation_pass.run(_s("TICK\nMX 9")) == _s("H 9\nTICK\nMZ 9")


def test_x_measurement_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(Basis.X)
    assert compilation_pass.run(_s("TICK\nM 0")) == _s("H 0\nTICK\nMX 0")
    assert compilation_pass.run(_s("TICK\nMZ 0")) == _s("H 0\nTICK\nMX 0")
    assert compilation_pass.run(_s("MX 12")) == _s("MX 12")
    assert compilation_pass.run(_s("MX 0")) == _s("MX 0")
    assert compilation_pass.run(_s("TICK\nMZ 9")) == _s("H 9\nTICK\nMX 9")


def test_edge_cases_measurement_basis() -> None:
    compilation_pass = ChangeMeasurementBasisPass(Basis.Z)
    assert compilation_pass.run(_s("H 0")) == _s("H 0")
    assert compilation_pass.run(_s("")) == _s("")
