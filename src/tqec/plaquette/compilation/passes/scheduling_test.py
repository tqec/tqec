import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.plaquette.compilation.passes.scheduling import ChangeSchedulePass, ScheduleMap


def _s(circuit: str) -> ScheduledCircuit:
    """Small helper to reduce clutter of long names."""
    return ScheduledCircuit.from_circuit(stim.Circuit(circuit))


def test_schedule_map_instantiation() -> None:
    ScheduleMap({})
    ScheduleMap({i: i for i in range(10)})
    ScheduleMap({i: i % 2 for i in range(10)})
    ScheduleMap({i: 2 * i for i in range(10)})


def test_simple_instantiation() -> None:
    ChangeSchedulePass({})
    ChangeSchedulePass({i: i for i in range(10)})
    ChangeSchedulePass({i: i % 2 for i in range(10)})
    ChangeSchedulePass({i: 2 * i for i in range(10)})


def test_identity() -> None:
    compilation_pass = ChangeSchedulePass({0: 0, 1: 1, 2: 2})
    circ = _s(
        "QUBIT_COORDS(0, 0) 0\n"
        "QUBIT_COORDS(0, 1) 1\n"
        "H 0\n"
        "TICK\n"
        "CX 0 1\n"
        "TICK\n"
        "M 1"
    )
    assert compilation_pass.run(circ) == circ


def test_new_moments() -> None:
    compilation_pass = ChangeSchedulePass({0: 0, 1: 1, 2: 3})
    circ = _s(
        "QUBIT_COORDS(0, 0) 0\n"
        "QUBIT_COORDS(0, 1) 1\n"
        "H 0\n"
        "TICK\n"
        "CX 0 1\n"
        "TICK\n"
        "M 1"
    )
    target_circ = _s(
        "QUBIT_COORDS(0, 0) 0\n"
        "QUBIT_COORDS(0, 1) 1\n"
        "H 0\n"
        "TICK\n"
        "CX 0 1\n"
        "TICK\n"
        "TICK\n"
        "M 1"
    )
    assert compilation_pass.run(circ) == target_circ
