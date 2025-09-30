from collections.abc import Callable
from typing import Any

import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap


def remap_qubit_indices(
    circuit: stim.Circuit,
    original_qubit_map: QubitMap | None = None,
    target_qubit_map: QubitMap | None = None,
    sort_key: Callable[[GridQubit], Any] = lambda q: (q.x, q.y),
) -> stim.Circuit:
    """Change qubit indices from ``circuit`` by using the provided ``target_qubit_map``.

    Args:
        circuit: original circuit that will be copied and changed by this
            function.
        original_qubit_map: qubit map representing the provided ``circuit``. If
            not provided, it will be automatically computed from ``circuit``.
        target_qubit_map: qubit map that should be used to index qubits in the
            circuit returned by this function. If not provided, this entry will
            be computed from ``original_qubit_map`` (or its default value) and
            ``sort_key`` by associating qubit indices from ``0`` to ``N-1`` to
            the ``N`` qubits in ``original_qubit_map`` in sorted order according
            to ``sort_key``.
        sort_key: callable used to sort qubits if ``target_qubit_map`` is not
            provided.

    Raises:
        KeyError: if ``original_qubit_map`` contains at least one qubit that is
            not in ``target_qubit_map``.

    Returns:
        a copy of the provided ``circuit`` with qubit indices changed to the
        provided ``target_qubit_map``.

    """
    if original_qubit_map is None:
        original_qubit_map = QubitMap.from_circuit(circuit)
    qubits = sorted(original_qubit_map.qubits, key=sort_key)
    if target_qubit_map is None:
        target_qubit_map = QubitMap.from_qubits(qubits)
    indices_mapping = {original_qubit_map[q]: target_qubit_map[q] for q in qubits}

    ret = stim.Circuit()
    for instruction in circuit:
        if isinstance(instruction, stim.CircuitRepeatBlock):
            ret.append(
                stim.CircuitRepeatBlock(
                    instruction.repeat_count,
                    remap_qubit_indices(
                        instruction.body_copy(),
                        original_qubit_map,
                        target_qubit_map,
                        sort_key,
                    ),
                )
            )
            continue
        ret.append(
            stim.CircuitInstruction(
                instruction.name,
                [
                    (indices_mapping[t.qubit_value] if t.qubit_value is not None else t)
                    for t in instruction.targets_copy()
                ],
                instruction.gate_args_copy(),
            )
        )
    return ret
