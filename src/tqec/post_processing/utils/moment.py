from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.manipulation import merge_instructions


@dataclass
class RepeatedMoments:
    repetitions: int
    moments: list[Moment | RepeatedMoments]


def iter_stim_circuit_by_moments(
    circuit: stim.Circuit, collected_before_use: bool = True
) -> Iterator[Moment | RepeatedMoments]:
    copy_func: Callable[[stim.Circuit], stim.Circuit] = (
        (lambda c: c.copy()) if collected_before_use else (lambda c: c)
    )
    cur_moment = stim.Circuit()
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            yield Moment(copy_func(cur_moment))
            cur_moment.clear()
            yield RepeatedMoments(
                inst.repeat_count,
                list(
                    iter_stim_circuit_by_moments(
                        inst.body_copy(), collected_before_use=True
                    )
                ),
            )
        elif inst.name == "TICK":
            yield Moment(copy_func(cur_moment))
            cur_moment.clear()
        else:
            cur_moment.append(inst)
    # No need to copy the last moment
    yield Moment(cur_moment)


def collect_moments(moments: list[Moment | RepeatedMoments]) -> stim.Circuit:
    if not moments:
        return stim.Circuit()

    ret = stim.Circuit()
    if isinstance(moments[0], Moment):
        ret += moments[0].circuit
    else:
        repeated_block = stim.Circuit("TICK") + collect_moments(moments[0].moments)
        ret.append(stim.CircuitRepeatBlock(moments[0].repetitions, repeated_block))

    for i in range(1, len(moments)):
        moment = moments[i]
        if isinstance(moment, Moment):
            ret.append(stim.CircuitInstruction("TICK"))
            ret += moment.circuit
        else:
            repeated_block = stim.Circuit("TICK") + collect_moments(moment.moments)
            ret.append(stim.CircuitRepeatBlock(moment.repetitions, repeated_block))
    return ret


def merge_moments(lhs: Moment, rhs: Moment) -> Moment:
    instructions = merge_instructions(list(lhs.instructions) + list(rhs.instructions))
    circuit = stim.Circuit()
    for inst in instructions:
        circuit.append(
            inst.name,
            sum(
                sorted(
                    inst.target_groups(),
                    key=lambda group: tuple(t.value for t in group),
                ),
                start=[],
            ),
            inst.gate_args_copy(),
        )
    return Moment(circuit)
