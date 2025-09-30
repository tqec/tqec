import warnings

import stim

from tqec.circuit.qubit_map import QubitMap
from tqec.utils.exceptions import TQECWarning


def subcircuit_only_on_indices(
    circuit: stim.Circuit, qubit_indices: frozenset[int]
) -> stim.Circuit:
    """Return a new circuit with only operations applied on qubit targets in ``qubit_indices``.

    Note:
        Non-qubit targets are not considered for filtering. That means that an
        operation only containing non-qubit targets (e.g., ``DETECTOR``) will
        not be filtered out. That also means that an operation applied on a
        qubit and a non-qubit target (e.g. ``CX rec[-1] 1``) will be in the
        returned circuit only if the qubit target(s) it is applied to (in the
        previous example, ``1``) is in ``qubit_indices``.

    Args:
        circuit: original circuit that should be filtered.
        qubit_indices: indices of qubits to keep in the resulting circuit.

    Returns:
        a new quantum circuit, only containing qubits with the indices provided.

    """
    ret = stim.Circuit()
    for instruction in circuit:
        if isinstance(instruction, stim.CircuitRepeatBlock):
            filtered_body = subcircuit_only_on_indices(instruction.body_copy(), qubit_indices)
            if len(filtered_body) != 0:
                ret.append(stim.CircuitRepeatBlock(instruction.repeat_count, filtered_body))
        elif instruction.name == "TICK":
            # Unconditionally append TICK annotations.
            ret.append(instruction)
        else:
            targets: list[stim.GateTarget] = []
            for target_group in instruction.target_groups():
                if all(
                    t.qubit_value is None or t.qubit_value in qubit_indices for t in target_group
                ):
                    targets.extend(target_group)
                if any(t.is_measurement_record_target for t in target_group):
                    warnings.warn(
                        "Found a measurement record target when filtering a "
                        "circuit. Filtering *might* remove qubit targets from "
                        "measurements instructions, and so *might* change the "
                        "measurement record. Be aware that the resulting "
                        "circuit might be invalid due to that behaviour.",
                        TQECWarning,
                    )
            if targets:
                ret.append(
                    stim.CircuitInstruction(instruction.name, targets, instruction.gate_args_copy())
                )
    return ret


def subcircuit(
    circuit: stim.Circuit, minx: float, maxx: float, miny: float, maxy: float
) -> stim.Circuit:
    """Filter a given circuit based on qubit coordinates.

    Only qubits within the bounding box provided by ``(minx, miny)`` and
    ``(maxx, maxy)`` will be kept in the resulting circuit. Only operations
    only involving kept qubits will be kept in the resulting circuit.

    Warning:
        Minimum bounds (``minx`` and ``miny``) are inclusive, but maximum ones
        (``maxx`` and ``maxy``) are exclusive.

    Args:
        circuit: original circuit that should be filtered.
        minx: X-coordinate of the top-left corner of the bounding box. Inclusive.
        maxx: X-coordinate of the bottom-right corner of the bounding box.
            Exclusive.
        miny: Y-coordinate of the top-left corner of the bounding box. Inclusive.
        maxy: Y-coordinate of the topbottom-right corner of the bounding box.
            Exclusive.

    Returns:
        a new quantum circuit, only containing qubits within the provided
        bounding box.

    """
    qubit_map = QubitMap.from_circuit(circuit)
    indices_to_keep = frozenset(
        i for i, q in qubit_map.i2q.items() if ((minx <= q.x < maxx) and (miny <= q.y < maxy))
    )
    return subcircuit_only_on_indices(circuit, indices_to_keep)
