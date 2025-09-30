from __future__ import annotations

import functools
import operator
from collections.abc import Callable, Iterator
from dataclasses import dataclass

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
    """Return an iterator over the moments of the provided ``circuit``.

    A moment is defined as all the operations between two ``TICK`` instructions. A moment can be
    empty (i.e., contains no instruction).

    Args:
        circuit: quantum circuit to extract moments from.
        collected_before_use: if ``False``, each call to ``next`` on the returned iterator will
            erase the previously returned circuit and replace it with a new one. Should only be set
            to ``False`` when iterating **AND** analysing moments one after the other, without the
            need to collect all the moments before.

    Returns:
        all the moments appearing in the provided ``circuit``, in apparition order. The quantum
        circuits representing each moment does **NOT** contain any ``TICK`` instruction.

    """
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
                list(iter_stim_circuit_by_moments(inst.body_copy(), collected_before_use=True)),
            )
        elif inst.name == "TICK":
            yield Moment(copy_func(cur_moment))
            cur_moment.clear()
        else:
            cur_moment.append(inst)
    # No need to copy the last moment
    yield Moment(cur_moment)


def collect_moments(moments: list[Moment | RepeatedMoments]) -> stim.Circuit:
    """Merge the provided ``moments`` into a ``stim.Circuit``."""
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
    """Merge two :class:`.Moment` instances into a single instance.

    Raises:
        TQECError if the resulting :class:`.Moment` instance is invalid, for example if it
            contains two operations using the same qubit at the same time step.

    """
    instructions = merge_instructions(list(lhs.instructions) + list(rhs.instructions))
    circuit = stim.Circuit()
    for inst in instructions:
        circuit.append(
            inst.name,
            functools.reduce(
                operator.iadd,
                sorted(
                    inst.target_groups(),
                    key=lambda group: tuple(t.value for t in group),
                ),
                [],
            ),
            inst.gate_args_copy(),
        )
    return Moment(circuit)
