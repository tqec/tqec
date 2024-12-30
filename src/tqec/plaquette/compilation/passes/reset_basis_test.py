import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.reset_basis import ChangeResetBasisPass
from tqec.plaquette.enums import Basis


def _s(circuit: str) -> ScheduledCircuit:
    """Small helper to reduce clutter of long names."""
    return ScheduledCircuit.from_circuit(stim.Circuit(circuit))


def test_compilation_pass_creation() -> None:
    ChangeResetBasisPass(Basis.X)
    ChangeResetBasisPass(Basis.Z)


def test_simple_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(Basis.Z)
    assert compilation_pass.run(_s("R 0")).get_circuit() == _s("R 0").get_circuit()
    assert compilation_pass.run(_s("RZ 0")) == _s("RZ 0")
    assert compilation_pass.run(_s("R 12")) == _s("R 12")
    assert compilation_pass.run(_s("RX 0\nTICK")) == _s("RZ 0\nTICK\nH 0")
    assert compilation_pass.run(_s("RX 9\nTICK")) == _s("RZ 9\nTICK\nH 9")

    # with pytest.raises(
    #     TQECException, match="^Found a RY instruction, that is not supported.$"
    # ):
    #     compilation_pass.run(_s("RY 0"))


def test_x_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(Basis.X)
    assert compilation_pass.run(_s("R 0")) == _s("RX 0\nTICK\nH 0")
    assert compilation_pass.run(_s("RZ 0")) == _s("RX 0\nTICK\nH 0")
    assert compilation_pass.run(_s("RX 12")) == _s("RX 12")
    assert compilation_pass.run(_s("RX 0")) == _s("RX 0")
    assert compilation_pass.run(_s("RZ 9")) == _s("RX 9\nTICK\nH 9")

    # with pytest.raises(
    #     TQECException, match="^Found a RY instruction, that is not supported.$"
    # ):
    #     compilation_pass.run(_s("RY 0"))


def test_edge_cases_reset_basis() -> None:
    compilation_pass = ChangeResetBasisPass(Basis.Z)
    assert compilation_pass.run(_s("H 0")) == _s("H 0")
    assert compilation_pass.run(_s("")) == _s("")


if __name__ == "__main__":
    test_simple_reset_basis()
