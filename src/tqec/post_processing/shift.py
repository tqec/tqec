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
            provided ``shifts`` contains more elements than the original
            number of dimensions in the arguments.

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
            provided ``shifts`` contains more elements than the original
            number of dimensions in the arguments.

    Returns:
        a copy of ``circuit`` with all the qubit coordinates shifted to positive
        values.

    """
    mins, _ = circuit_bounding_box(circuit)
    shifts = [-m if stick_to_origin or m < 0 else 0 for m in mins]
    return shift_qubits(circuit, *shifts, also_shift_detectors=also_shift_detectors)


def transform_spatial_coordinates(
    circuit: stim.Circuit,
    scale: float = 1.0,
    offset: tuple[float, float] = (0.0, 0.0),
) -> stim.Circuit:
    """Apply the affine map ``(x, y) -> scale * (x, y) + offset`` to the provided circuit.

    The map applies to the first two arguments (``x`` and ``y``) of ``QUBIT_COORDS``
    and ``DETECTOR`` instructions. ``SHIFT_COORDS`` arguments are relative
    displacements, so they are only multiplied by ``scale``. The offset applies
    once to absolute positions and must not accumulate with each shift. With that
    rule, the absolute coordinates stim computes for every qubit and detector are
    mapped by the same affine map. Any further argument (e.g., the time
    coordinate) is left unchanged, ``REPEAT`` blocks are transformed recursively and
    all other instructions, including their targets, are copied as is.

    Args:
        circuit: circuit whose spatial coordinates should be transformed.
        scale: multiplicative factor applied to the ``x`` and ``y`` coordinates.
        offset: ``(x, y)`` translation applied after the scaling.

    Returns:
        a new ``stim.Circuit`` instance with transformed spatial coordinates.

    """
    ret = stim.Circuit()
    for instr in circuit:
        if isinstance(instr, stim.CircuitRepeatBlock):
            ret.append(
                stim.CircuitRepeatBlock(
                    instr.repeat_count,
                    transform_spatial_coordinates(instr.body_copy(), scale, offset),
                )
            )
        elif instr.name in ("QUBIT_COORDS", "DETECTOR"):
            args = instr.gate_args_copy()
            ret.append(
                instr.name,
                instr.targets_copy(),
                [a * scale + offset[i] if i < 2 else a for i, a in enumerate(args)],
            )
        elif instr.name == "SHIFT_COORDS":
            args = instr.gate_args_copy()
            ret.append(
                instr.name,
                instr.targets_copy(),
                [a * scale if i < 2 else a for i, a in enumerate(args)],
            )
        else:
            ret.append(instr)
    return ret


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
    qubit_coordinates = circuit.get_final_qubit_coordinates()
    if not qubit_coordinates:
        return [], []

    coordinates = numpy.array(list(qubit_coordinates.values()))
    return list(numpy.min(coordinates, axis=0)), list(numpy.max(coordinates, axis=0))
