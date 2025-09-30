import stim


def add_tick_coordinate_to_detectors(circuit: stim.Circuit) -> stim.Circuit:
    """Add a coordinate containing the current moment index to each detector."""
    ret = stim.Circuit()
    num_ticks: int = 0
    for instruction in circuit.flattened():
        assert not isinstance(instruction, stim.CircuitRepeatBlock)
        assert instruction.name != "SHIFT_COORDS"
        if instruction.name == "TICK":
            num_ticks += 1
            ret.append(instruction)
        elif instruction.name == "DETECTOR":
            ret.append(
                stim.CircuitInstruction(
                    instruction.name,
                    instruction.targets_copy(),
                    [*instruction.gate_args_copy(), num_ticks],
                )
            )
        else:
            ret.append(instruction)
    return ret
