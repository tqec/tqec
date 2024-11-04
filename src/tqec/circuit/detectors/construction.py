from __future__ import annotations

import stim

from tqec.circuit.detectors.flow import build_flows_from_fragments
from tqec.circuit.detectors.fragment import (
    Fragment,
    FragmentLoop,
    split_stim_circuit_into_fragments,
)
from tqec.circuit.detectors.match import (
    MatchedDetector,
    match_detectors_from_flows_shallow,
)
from tqec.circuit.detectors.predicates import is_valid_input_circuit
from tqec.exceptions import TQECException


def _detectors_to_circuit(
    detectors: list[MatchedDetector],
    shift_coords: tuple[float, ...] = (0, 0, 0),
) -> stim.Circuit:
    """Transform a list of detectors into a circuit.

    Args:
        detectors: detectors that will be included in the returned circuit.

    Returns:
        A `stim.Circuit` instance containing all the provided detectors.
    """
    circuit = stim.Circuit()
    if any(shift != 0 for shift in shift_coords) and detectors:
        circuit.append("SHIFT_COORDS", [], shift_coords)

    for detector in detectors:
        circuit.append(detector.to_instruction())
    return circuit


def annotate_detectors_automatically(circuit: stim.Circuit) -> stim.Circuit:
    """Insert detectors into the provided circuit instance.

    This is the main user-facing function to automatically insert detectors into
    a quantum circuit composed of Clifford operations. The provided circuit should
    check some pre-conditions to be accepted, which are detailed in details below.

    First and foremost, the provided circuit should check the pre-conditions listed
    in the documentation of :func:`split_stim_circuit_into_fragments`.

    Args:
        circuit: circuit to insert detectors in.

    Returns:
        A new `stim.Circuit` instance with automatically computed detectors.
    """
    potential_error_reason = is_valid_input_circuit(circuit)
    if potential_error_reason is not None:
        raise TQECException(potential_error_reason)

    fragments = split_stim_circuit_into_fragments(circuit)
    qubit_coords_map: dict[int, tuple[float, ...]] = {
        q: tuple(coords) for q, coords in circuit.get_final_qubit_coordinates().items()
    }
    return compile_fragments_to_circuit_with_detectors(fragments, qubit_coords_map)


def compile_fragments_to_circuit(
    fragments: list[Fragment | FragmentLoop],
) -> stim.Circuit:
    circuit = stim.Circuit()

    for fragment in fragments:
        if isinstance(fragment, Fragment):
            circuit += fragment.circuit
        else:  # isinstance(fragment, FragmentLoop):
            loop_body = compile_fragments_to_circuit(fragment.fragments)
            circuit += loop_body * fragment.repetitions
    return circuit


def _tick_circuit() -> stim.Circuit:
    return stim.Circuit("TICK")


def _insert_before_last_tick_instruction(
    circuit: stim.Circuit, added_circuit: stim.Circuit
) -> stim.Circuit:
    if circuit[-1].name == "TICK":
        return circuit[:-1] + added_circuit + _tick_circuit()
    else:
        return circuit + added_circuit


def _append_fragment_to_circuit(
    circuit: stim.Circuit,
    fragment: Fragment | FragmentLoop,
    detectors: list[MatchedDetector],
    qubit_coords_map: dict[int, tuple[float, ...]],
    shifts: tuple[float, ...] = (0, 0, 0),
) -> None:
    detectors_circuit = _detectors_to_circuit(detectors, shift_coords=shifts)
    if isinstance(fragment, Fragment):
        circuit += _insert_before_last_tick_instruction(
            fragment.circuit, detectors_circuit
        )
    else:  # isinstance(fragment, FragmentLoop):
        loop_body = compile_fragments_to_circuit_with_detectors(
            fragment.fragments, qubit_coords_map
        )
        circuit += (
            _insert_before_last_tick_instruction(loop_body, detectors_circuit)
            * fragment.repetitions
        )


def compile_fragments_to_circuit_with_detectors(
    fragments: list[Fragment | FragmentLoop],
    qubit_coords_map: dict[int, tuple[float, ...]],
) -> stim.Circuit:
    flows = build_flows_from_fragments(fragments)
    detectors_from_flows = match_detectors_from_flows_shallow(flows, qubit_coords_map)

    circuit = stim.Circuit()
    number_of_spatial_coordinates = len(next(iter(qubit_coords_map.values()), []))
    shifts = tuple(0 for _ in range(number_of_spatial_coordinates)) + (1,)

    # Add the first moment without any shift
    _append_fragment_to_circuit(
        circuit, fragments[0], detectors_from_flows[0], qubit_coords_map
    )
    # Add the other moments
    for fragment, detectors in zip(fragments[1:], detectors_from_flows[1:]):
        _append_fragment_to_circuit(
            circuit, fragment, detectors, qubit_coords_map, shifts=shifts
        )

    return circuit
