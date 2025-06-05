import stim

from tqec.circuit.moment import Moment
from tqec.post_processing.utils.moment import RepeatedMoments


def remove_empty_moments(
    circuit: stim.Circuit,
    remove_leading_tick: bool = True,
    remove_trailing_tick: bool = True,
) -> stim.Circuit:
    """Remove empty moments in a circuit.

    This function removes empty moments (delimited by ``TICK`` instructions) in
    the provided circuit, returning a copy of the circuit without the empty
    moments.

    Note:
        This function follows ``stim`` convention on ``REPEAT`` blocks to:

        1. not include any ``TICK`` instruction just before the ``REPEAT`` block,
        2. include a ``TICK`` instruction at the beginning of the repeated block,
        3. not include a ``TICK`` instruction at the end of the repeated block.

        The instruction following a ``REPEAT`` block with ``stim gen`` is often
        not a ``TICK`` because only the last measurements on data-qubits are left
        to perform and so they do not overlap with the last measurements within
        the repeated block. For this reason, this function do not enforce
        anything about the instruction following a ``REPEAT`` block:

        - if it is not a ``TICK`` in the original circuit, no ``TICK`` is
          inserted,
        - if there are one or more consecutive ``TICK`` instructions, only one
          will be left (removing empty moments).

    Args:
        circuit: circuit to remove empty moments from.
        remove_leading_tick: whether to remove the first instruction of
            ``circuit`` if it is a ``TICK`` instruction. Note that this parameter
            is not recursively forwarded to repeated blocks, see the note.
        remove_trailing_tick: whether to remove the last instruction of
            ``circuit`` if it is a ``TICK`` instruction. Note that this parameter
            is not recursively forwarded to repeated blocks, see the note.

    Returns:
        A quantum circuit without any empty moment and with ``REPEAT`` blocks
        adhering to the conventions detailed in the note above.

    """
    ret = stim.Circuit()
    # Start with a virtual TICK if the user wants to remove empty moments at the
    # beginning of the provided circuit. Else, any other instruction that is not
    # a TICK would work and avoid the removal of the first instruction if it is
    # a TICK.
    previous_instruction = (
        stim.CircuitInstruction("TICK")
        if remove_leading_tick
        else stim.CircuitInstruction("SHIFT_COORDS", [], [0])
    )
    for inst in circuit:
        # If we have two (or more) consecutive TICK instructions, do not append
        # any except the first one.
        if inst.name == previous_instruction.name == "TICK":
            continue
        # If we have a REPEAT block, be careful about the conventions.
        if isinstance(inst, stim.CircuitRepeatBlock):
            # Check convention 1 about the instruction before the REPEAT instruction
            if ret[-1].name == "TICK":
                ret = ret[:-1]
            # Check conventions 2 and 3 about the repeated block.
            repeated_block = stim.Circuit("TICK") + remove_empty_moments(
                inst.body_copy(), remove_leading_tick=True, remove_trailing_tick=True
            )
            ret.append(stim.CircuitRepeatBlock(inst.repeat_count, repeated_block))
        else:
            ret.append(inst)
        previous_instruction = inst
    # If the last instruction is a TICK, that's an empty moment, remove it.
    if previous_instruction.name == "TICK" and remove_trailing_tick:
        return ret[:-1]
    return ret


def _remove_empty_moments_inline(moments: list[Moment | RepeatedMoments]) -> None:
    i = 0
    while i < len(moments):
        moment = moments[i]
        if isinstance(moment, Moment):
            if moment.is_empty:
                moments.pop(i)
            else:
                i += 1
        else:
            _remove_empty_moments_inline(moment.moments)
            if len(moment.moments) == 0:
                moments.pop(i)
            else:
                i += 1
