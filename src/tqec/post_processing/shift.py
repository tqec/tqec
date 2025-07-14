from itertools import zip_longest

import numpy
import stim


def shift_qubits(
    circuit: stim.Circuit,
    *shifts: float,
    also_shift_detectors: bool = True,
) -> stim.Circuit:
    """Shift the qubit coordinates of the provided circuit by ``shifts``.

    Args:
        circuit: circuit containing qubits to shift.
        shifts: a list of shifts to apply to each dimension.
        also_shift_detectors: if ``True``, coordinates of ``DETECTOR``
            instructions are also shifted. Note that this might introduce
            additional dimensions to the ``DETECTOR`` instructions if the
            provided ``shifts`` is contains more elements than the original
            number of dimensions in the arguments.

    Raises:
        TQECError: if any ``QUBIT_COORDS`` instruction in the provided
            ``circuit`` has a number of arguments (i.e., dimensions) that is
            different from the provided number of ``shifts``.

    Returns:
        a new ``stim.Circuit`` instance with qubit coordinates shifted by
        ``shifts``.

    """
    ret = stim.Circuit()
    for instr in circuit:
        if isinstance(instr, stim.CircuitRepeatBlock):
            ret.append(
                stim.CircuitRepeatBlock(
                    instr.repeat_count,
                    shift_qubits(
                        instr.body_copy(),
                        *shifts,
                        also_shift_detectors=also_shift_detectors,
                    ),
                )
            )
        elif instr.name == "QUBIT_COORDS" or (also_shift_detectors and instr.name == "DETECTOR"):
            args = instr.gate_args_copy()
            ret.append(
                instr.name,
                instr.targets_copy(),
                [arg + s for arg, s in zip_longest(args, shifts, fillvalue=0)],
            )
        else:
            ret.append(instr)
    return ret


def shift_to_only_positive(
    circuit: stim.Circuit,
    stick_to_origin: bool = True,
    also_shift_detectors: bool = True,
) -> stim.Circuit:
    """Shift the provided circuit so that it only operates on qubits with positive coordinates.

    Args:
        circuit: quantum circuit to shift.
        stick_to_origin: if ``True``, coordinates that are already positive may
            still be shifted so that the minimum coordinate is ``0``.
        also_shift_detectors: if ``True``, coordinates of ``DETECTOR``
            instructions are also shifted. Note that this might introduce
            additional dimensions to the ``DETECTOR`` instructions if the
            provided ``shifts`` is contains more elements than the original
            number of dimensions in the arguments.

    Returns:
        a copy of ``circuit`` with all the qubit coordinates shifted to positive
        values.

    """
    mins, _ = circuit_bounding_box(circuit)
    shifts = [-m if stick_to_origin or m < 0 else 0 for m in mins]
    return shift_qubits(circuit, *shifts, also_shift_detectors=also_shift_detectors)


def circuit_bounding_box(
    circuit: stim.Circuit,
) -> tuple[list[float], list[float]]:
    """Get the bounding box of the qubits in the provided circuit.

    Note:
        This function uses ``stim.Circuit.get_final_qubit_coordinates`` to get
        qubit coordinates. As such, it returns the "final" bounding box. As long
        as the qubit coordinates are not redefined in the provided circuit, the
        returned bounding box is valid through the whole circuit.

    Args:
        circuit: circuit used to compute the bounding box.

    Returns:
        a tuple ``(mins, maxes)`` containing 2 lists containing the minimum
        (resp. maximum) coordinate found in each dimension.
        If the circuit does not contain any ``QUBIT_COORDS`` instruction, the
        returned lists are empty.

    """
    coordinates = numpy.array(list(circuit.get_final_qubit_coordinates().values()))
    return list(numpy.min(coordinates, axis=0)), list(numpy.max(coordinates, axis=0))
