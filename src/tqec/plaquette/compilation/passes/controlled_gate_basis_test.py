import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.enums import Basis
from tqec.plaquette.compilation.passes.controlled_gate_basis import (
    ChangeControlledGateBasisPass,
)
from tqec.plaquette.compilation.passes.transformer import (
    ScheduleConstant,
    ScheduleOffset,
)


def _s(circuit: str) -> ScheduledCircuit:
    """Small helper to reduce clutter of long names."""
    return ScheduledCircuit.from_circuit(stim.Circuit(circuit))


def test_compilation_pass_creation() -> None:
    ChangeControlledGateBasisPass(Basis.X, ScheduleConstant(0), ScheduleConstant(6))
    ChangeControlledGateBasisPass(Basis.Z, ScheduleConstant(0), ScheduleConstant(6))
    ChangeControlledGateBasisPass(Basis.X, ScheduleOffset(-1), ScheduleOffset(1))
    ChangeControlledGateBasisPass(Basis.Z, ScheduleOffset(-1), ScheduleOffset(1))


def test_simple_controlled_gate_basis() -> None:
    compilation_pass = ChangeControlledGateBasisPass(
        Basis.X, ScheduleOffset(-1), ScheduleOffset(1)
    )
    assert compilation_pass.run(_s("TICK\nCX 0 1\nTICK")) == _s("TICK\nCX 0 1\nTICK")
    assert compilation_pass.run(_s("TICK\nCZ 0 1\nTICK")) == _s(
        "H 1\nTICK\nCX 0 1\nTICK\nH 1"
    )
    assert compilation_pass.run(_s("TICK\nCZ 1 0\nTICK")) == _s(
        "H 0\nTICK\nCX 1 0\nTICK\nH 0"
    )
    assert (
        compilation_pass.run(_s("RX 0\nTICK\nCZ 0 1\nTICK\nMX 0")).get_circuit()
        == _s("RX 0\nH 1\nTICK\nCX 0 1\nTICK\nMX 0\nH 1").get_circuit()
    )


def test_controlled_gate_basis_schedule_constant() -> None:
    compilation_pass = ChangeControlledGateBasisPass(
        Basis.X, ScheduleConstant(0), ScheduleConstant(6)
    )
    qubit_map = QubitMap({i: GridQubit(i, i) for i in [0, 1]})
    for sched in range(1, 6):
        circ = ScheduledCircuit([Moment(stim.Circuit("CZ 0 1"))], [sched], qubit_map)
        compiled_circ = compilation_pass.run(circ)
        assert compiled_circ == ScheduledCircuit(
            [
                Moment(stim.Circuit("H 1")),
                Moment(stim.Circuit("CX 0 1")),
                Moment(stim.Circuit("H 1")),
            ],
            [0, sched, 6],
            qubit_map,
        )
