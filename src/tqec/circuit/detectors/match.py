from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterator, Mapping

import numpy
import stim

from tqec.circuit.detectors.boundary import BoundaryStabilizer
from tqec.circuit.detectors.flow import FragmentFlows, FragmentLoopFlows
from tqec.circuit.detectors.match_utils.cover import find_exact_cover_sat
from tqec.circuit.detectors.measurement import RelativeMeasurementLocation
from tqec.exceptions import TQECException


@dataclass(frozen=True)
class MatchedDetector:
    """Represents an automatically computed detector."""

    coords: tuple[float, ...]
    measurements: frozenset[RelativeMeasurementLocation]
    resets: tuple[frozenset[int], ...]

    def __hash__(self) -> int:
        return hash(self.measurements)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MatchedDetector):
            return False
        if self.measurements != other.measurements:
            return False
        return numpy.allclose(self.coords, other.coords)

    def to_instruction(self) -> stim.CircuitInstruction:
        targets = [
            stim.target_rec(m.offset)
            for m in sorted(
                self.measurements, key=lambda measurement: -measurement.offset
            )
        ]
        return stim.CircuitInstruction("DETECTOR", targets, list(self.coords))

    def with_time_coordinate(self, time_coordinate: float) -> MatchedDetector:
        return MatchedDetector(
            self.coords + (time_coordinate,), self.measurements, self.resets
        )


def match_detectors_from_flows_shallow(
    flows: list[FragmentFlows | FragmentLoopFlows],
    qubit_coordinates: dict[int, tuple[float, ...]],
) -> list[list[MatchedDetector]]:
    """Match detectors in the provided fragments.

    This function only performs a shallow search. Read attentively the warning and
    return sections of this documentation to understand how to use it correctly.

    Warning:
        This function only performs a shallow computation! It will consider REPEAT
        constructs as an atomic fragment with outgoing stabilizers on both sides,
        but will not recurse in the loop.

        In practice, this limitation should not be a huge issue. As the loops are
        still considered as an atomic operation, resets in the last fragment of
        the loop body and measurements in the first fragment of the loop body are
        still accounted for.
        This means that if the loop body only implements a simple QEC round (e.g.,
        surface code or repetition code), or more generally if the loop body is
        considered as a single :class:`Fragment` instance, the detectors will be
        appropriately matched and returned.

    Args:
        flows: a list of fragment flow to search detectors in.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to annotate
            the matched detectors with the coordinates from the qubits involved in the
            measurement forming the detector.

    Returns:
        the list of all the detectors found. These detectors are only valid if inserted
        at the end of the fragment represented by the last provided flow in the input
        parameter `flows`. If the last provided flow is an instance of
        :class:`FragmentLoopFlows` then the returned detectors should be inserted at
        the end of the loop body.
    """
    detectors: list[list[MatchedDetector]] = [
        match_detectors_within_fragment(flow, qubit_coordinates) for flow in flows
    ]
    for i in range(1, len(flows)):
        detectors[i].extend(
            match_boundary_stabilizers(flows[i - 1], flows[i], qubit_coordinates)
        )

    # Set the time coordinate of each detector.
    detectors_groups: list[dict[int, list[MatchedDetector]]] = []
    for detectors_in_moment in detectors:
        groups: dict[int, list[MatchedDetector]] = {}
        for d in detectors_in_moment:
            groups.setdefault(len(d.measurements), []).append(d)
        detectors_groups.append(groups)
    max_groups = max(len(g) for g in detectors_groups)
    increment = 1 / max_groups if max_groups != 0 else 1

    detectors_with_time: list[list[MatchedDetector]] = []
    for group in detectors_groups:
        detectors_with_time.append(
            sum(
                [
                    [
                        d.with_time_coordinate(i * increment)
                        for d in group[num_measurements]
                    ]
                    for i, num_measurements in enumerate(sorted(group.keys()))
                ],
                start=[],
            )
        )
    return detectors_with_time


def match_detectors_within_fragment(
    flows: FragmentFlows | FragmentLoopFlows,
    qubit_coordinates: Mapping[int, tuple[float, ...]],
) -> list[MatchedDetector]:
    """Match all the detectors that can be resolved without considering
    neighbouring fragments.

    Some detectors only include measurements from one fragment. This is for example the
    case during the initialisation of any code: some measurements from the first round
    have a pre-defined value that should be constant in the absence of errors.

    Note that this function ignores "trivial" flows to avoid trivial detectors to be
    matched on some particular cases (e.g., 1-round repetition code).

    Args:
        flows: pre-computed flows for the fragment of interest. If any detector
            is found, the involved flow(s) will be removed from the provided instance.
            This means that **this parameter may be mutated inline**.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to annotate
            the matched detectors with the coordinates from the qubits involved in the
            measurement forming the detector.

    Returns:
        the list of all the detectors found.
    """
    matched_detectors: list[MatchedDetector] = []
    matched_detectors.extend(
        _match_non_propagating_non_trivial_flows_inline(
            flows.creation, qubit_coordinates
        )
    )
    matched_detectors.extend(
        _match_non_propagating_non_trivial_flows_inline(
            flows.destruction, qubit_coordinates
        )
    )
    return matched_detectors


def _match_non_propagating_non_trivial_flows_inline(
    boundary_stabilizers: list[BoundaryStabilizer],
    qubit_coordinates: Mapping[int, tuple[float, ...]],
) -> list[MatchedDetector]:
    """Match all the detectors that can be trivially resolved and remove the
    matched boundary stabilizers from the provided list.

    This function try to find a trivial match for each of the provided boundary
    stabilizers. A trivial match is defined here as a flow that is fully
    collapsed by the collapsing operations it encounters, stopping its
    propagation.

    Note that an approximation is made in this function: trivial flows (not to
    be confused with trivial matches) are excluded from the search because they
    generate unwanted detectors.

    This function **mutates its input in-place**.

    This function guarantees the following:

    ```py
    boundary_stabilizers = []   # Fill it!
    qubit_coordinates = {}      # Fill it!
    len_bs_before = len(boundary_stabilizers)

    detectors = _match_non_propagating_non_trivial_flows_inline(
        boundary_stabilizers, qubit_coordinates
    )
    assert len_bs_before == len(detectors) + len(boundary_stabilizers)
    ```

    Args:
        boundary_stabilizers: list of boundary stabilizers to match trivially.
            This list is modified in-place: when a detector is found, the
            boundary_stabilizer associated with this detector is removed from
            the list.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to annotate
            the matched detectors with the coordinates from the qubits involved in the
            measurement forming the detector.

    Returns:
        all matched detectors.
    """
    matched_detectors: list[MatchedDetector] = []
    non_propagating_flows_indices = list(
        _find_non_propagating_non_trivial_flows(boundary_stabilizers)
    )

    # Note that the call to sorted here is not really needed as
    # _find_non_propagating_non_trivial_flows guarantees that the returned indices
    # are sorted, so `non_propagating_flows_indices[::-1]` should be enough.
    # We still call sorted here to avoid subtle bugs in case the above-mentioned
    # post-condition is changed one day, and because the number of indices
    # is not expected to be large here.
    for i in sorted(non_propagating_flows_indices, reverse=True):
        flow = boundary_stabilizers.pop(i)
        matched_detectors.append(
            MatchedDetector(
                coords=flow.coordinates(qubit_coordinates),
                measurements=frozenset(flow.measurements),
                resets=(flow.resets_qubits,),
            )
        )

    return matched_detectors


def _find_non_propagating_non_trivial_flows(
    boundary_stabilizers: list[BoundaryStabilizer],
) -> Iterator[int]:
    """Find all the boundary stabilizers that do not have any anti-commuting
    collapsing operations and that are fully collapsed by the commuting
    operations.

    Args:
        boundary_stabilizers: the boundary stabilizers to search in.

    Yields:
        indices (in ascending order) of boundary stabilizers in the provided
        `boundary_stabilizers` list that are non-trivial and fully collapsed
        by the commuting operations.
    """
    for i, stabilizer in enumerate(boundary_stabilizers):
        if (
            not stabilizer.is_trivial()
            and not stabilizer.has_anticommuting_operations
            and stabilizer.after_collapse.non_trivial_pauli_count == 0
        ):
            yield i


def match_boundary_stabilizers(
    left_flows: FragmentFlows | FragmentLoopFlows,
    right_flows: FragmentFlows | FragmentLoopFlows,
    qubit_coordinates: Mapping[int, tuple[float, ...]],
    perform_sanity_check: bool = True,
) -> list[MatchedDetector]:
    """Match detectors using the boundary stabilizers between the two given
    flows.

    This function try to match detectors that will be valid at the end of
    `right_flows` by looking at destruction boundary stabilizers back-propagated
    from measurements in `right_flows` and creation boundary stabilizers
    propagated from resets in `left_flows`.
    The above 2 stabilizer types should meet at the interface between the two
    provided flows. If we find any creation stabilizer matching (i.e. being
    equal to) any other destruction stabilizer, these form a detector!

    This function **mutates `left_flows` and `right_flows` in-place** if
    a detector is found.

    Args:
        left_flows: pre-computed flows from the left fragment.
        right_flows: pre-computed flows from the right fragment.
        qubit_coordinates: _description_
        perform_sanity_check: If True and if `right_flows` is an instance of
            :class:`FragmentLoopFlows`, detectors found between `left_flows`
            and `right_flows` are compared to the detectors found between the
            last and first fragments of the body of `right_flows`. If the two
            sets are not equal, an exception is raised. Defaults to True.

    Raises:
        TQECException: if the sanity check does not pass.

    Returns:
        all matched detectors.
    """
    matched_detectors: list[MatchedDetector] = []

    # Sanity check: if the provided right flow is a FragmentLoopFlows, this function
    #     will compute the detectors between the first iteration of the loop and the
    #     previous fragment. If the circuit is valid, the computed detectors should
    #     be exactly the same between the fragments of two loop bodies (if the loop
    #     is repeated at least twice).
    #     Because the matching functions are modifying flows in-place, we pre-compute the
    #     detectors here on copies and will compare them before returning.
    should_sanity_check = perform_sanity_check and (
        isinstance(right_flows, FragmentLoopFlows) and right_flows.repeat > 1
    )
    if should_sanity_check:
        matched_detectors_within_loop = match_boundary_stabilizers(
            # Type checking is disabled below. right_flows is guaranteed to be of type
            # FragmentLoopFlows (per the value of should_sanity_check), and so have a
            # "fragment_flows" attribute.
            deepcopy(right_flows.fragment_flows[-1]),  # type: ignore
            deepcopy(right_flows.fragment_flows[0]),  # type: ignore
            qubit_coordinates,
        )

    # 0. Combining anti-commuting stabilizers
    # We try to combine stabilizers anti-commuting with their collapsing operations
    # here because:
    #   1. the `try_merge_anticommuting_flows` method does not consider commuting
    #      stabilizers, so calling this method has the same cost now and after a first
    #      round of matching.
    #   2. the different matching methods are now quite efficient and so should not
    #      suffer too much (in terms of performance) from the commuting stabilizers
    #      potentially added at this step.
    # If commuting stabilizer computation is experiencing performance issues, it might
    # be interesting to perform this step AFTER a first round of commuting stabilizer
    # matching, and repeating the matching steps after to match newly added commuting
    # stabilizers into detectors.
    left_flows.try_merge_anticommuting_flows()
    right_flows.try_merge_anticommuting_flows()

    # 1. Match stabilizers 1-to-1 without anti-commuting collapses
    matched_detectors.extend(
        _match_commute_stabilizers(left_flows, right_flows, qubit_coordinates)
    )

    # 2. Try to match remaining stabilizers without any anti-commuting collapses
    #    by trying to find covers.
    matched_detectors.extend(
        _match_by_disjoint_cover(left_flows, right_flows, qubit_coordinates)
    )

    # Perform the sanity check if needed.
    if should_sanity_check:
        if set(matched_detectors_within_loop) != set(matched_detectors):
            raise TQECException(
                f"The set of detectors computed from measurements in\n{left_flows}\n"
                f"and\n{right_flows}\nis not the same as the set of detectors computed "
                "from measurements between two loop body repetitions. Is your QEC "
                "circuit valid?"
            )
    return matched_detectors


def _match_commute_stabilizers(
    left_flows: FragmentFlows | FragmentLoopFlows,
    right_flows: FragmentFlows | FragmentLoopFlows,
    qubit_coordinates: Mapping[int, tuple[float, ...]],
) -> list[MatchedDetector]:
    """Take stabilizers from two contiguous fragments and try to match them.

    Let use the two fragment instances `f1` and `f2` such that `f1` is just
    before `f2`. There is a stabilizer boundary at the interface between `f1`
    and `f2`. Considering only the stabilizers that propagated forward from
    the resets of `f1` and commuted with all the measurements they encountered
    as well as the stabilizers that propagated backwards from the measurements
    of `f2` and commuted with all the resets they encountered, we can try to
    match these stabilizers at the interface.

    This method performs a "dumb" matching between stabilizers, only matching
    if one stabilizer from `f1` exactly matches with one stabilizer from `f2`.

    Args:
        left_flows: flows of the fragment that comes first.
        right_flows: flows of the fragment that comes second.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to
            annotate the matched detectors with the coordinates from the qubits
            involved in the measurement forming the detector.

    Returns:
        the list of all the detectors found.
    """
    detectors: list[MatchedDetector] = []
    left_flows_indices_to_remove: list[int] = []

    for ilhs, creation_flow in enumerate(left_flows.creation):
        if creation_flow.has_anticommuting_operations:
            continue

        right_flows_index_to_remove: int | None = None
        for irhs, destruction_flow in enumerate(right_flows.destruction):
            if destruction_flow.has_anticommuting_operations:
                continue

            # If the stabilizers are not exactly the same, this is not a match.
            if creation_flow.after_collapse != destruction_flow.after_collapse:
                continue
            # Else, it is a match!
            measurements = frozenset(
                m.offset_by(-right_flows.total_number_of_measurements)
                for m in creation_flow.measurements
            ) | frozenset(destruction_flow.measurements)
            resets = (creation_flow.resets_qubits, destruction_flow.resets_qubits)
            detectors.append(
                MatchedDetector(
                    coords=destruction_flow.coordinates(qubit_coordinates),
                    measurements=measurements,
                    resets=resets,
                )
            )
            left_flows_indices_to_remove.append(ilhs)
            right_flows_index_to_remove = irhs
            # break here because the creation stabilizer is matched and
            # will be removed, so there is no point trying to match it with
            # other destruction stabilizers.
            break
        # Here, we finished the iteration on right_flows, so we can remove
        # the matched flows.
        if right_flows_index_to_remove is not None:
            right_flows.remove_destruction(right_flows_index_to_remove)

    # Here, we finished the iteration on left_flows, so we can remove the
    # matched flows.
    left_flows.remove_creations(left_flows_indices_to_remove)
    return detectors


def _match_boundary_stabilizers_by_disjoint_cover(
    target_stabilizers: list[BoundaryStabilizer],
    covering_stabilizers: list[BoundaryStabilizer],
    qubit_coordinates: Mapping[int, tuple[float, ...]],
    target_is_creation: bool,
) -> tuple[list[MatchedDetector], list[int]]:
    """Try to match stabilizers by finding a cover.

    This function will try to match each of the stabilizers found in
    `target_stabilizers` with several stabilizers from `covering_stabilizers`.
    This is a one-to-many relationship: one stabilizer from `target_stabilizers`
    will be matched to many stabilizers from `covering_stabilizers`.

    Args:
        target_stabilizers: list of stabilizers to try to separately match with
            several stabilizers from `covering_stabilizers`.
        covering_stabilizers: list of stabilizers that can be combined together to
            match with one stabilizer from `target_stabilizers`.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to
            annotate the matched detectors with the coordinates from the qubits
            involved in the measurement forming the detector.
        target_is_creation: `True` if the provided `target_stabilizers` are
            creation stabilizers, else `False`.
    Returns:
        the list of all the detectors found as well as the indices of stabilizers
        from `target_stabilizers` that have been used and should be removed from
        the considered stabilizers.
    """
    detectors: list[MatchedDetector] = []
    targets_to_remove: list[int] = []
    # For each target, try to find a cover.
    for i, target in enumerate(target_stabilizers):
        # Try to find the cover. If unsuccessful, skip `target` and continue the loop.
        # Else, a detector is matched, so insert it into the returned list and mark
        # `target` as "to remove".
        cover_indices = find_exact_cover_sat(
            target.after_collapse, [cs.after_collapse for cs in covering_stabilizers]
        )
        if cover_indices is None:
            continue

        measurements_involved_in_cover: frozenset[RelativeMeasurementLocation] = (
            frozenset()
        )
        resets_qubits_involved_in_cover: frozenset[int] = frozenset()
        for j in cover_indices:
            # We know for sure that each boundary stabilizer commutes with the collapsing
            # operations on the boundary. That means that if a measurement is appearing
            # an even number of times, the associated flow would simply cancel out, not
            # touching the measurement. The symmetric difference operator is used for that
            # purpose here.
            measurements_involved_in_cover ^= set(covering_stabilizers[j].measurements)
            resets_qubits_involved_in_cover ^= covering_stabilizers[j].resets_qubits

        measurements = frozenset(target.measurements) | measurements_involved_in_cover
        resets = (
            (target.resets_qubits, resets_qubits_involved_in_cover)
            if target_is_creation
            else (resets_qubits_involved_in_cover, target.resets_qubits)
        )
        detectors.append(
            MatchedDetector(
                coords=target.coordinates(qubit_coordinates),
                measurements=measurements,
                resets=resets,
            )
        )
        targets_to_remove.append(i)
    return detectors, targets_to_remove


def _match_by_disjoint_cover(
    left_flows: FragmentFlows | FragmentLoopFlows,
    right_flows: FragmentFlows | FragmentLoopFlows,
    qubit_coordinates: Mapping[int, tuple[float, ...]],
) -> list[MatchedDetector]:
    """Try to match stabilizers by finding a cover.

    Args:
        left_flows: flows of the fragment that comes first.
        right_flows: flows of the fragment that comes second.
        qubit_coordinates: a mapping from qubit indices to coordinates. Used to
            annotate the matched detectors with the coordinates from the qubits
            involved in the measurement forming the detector.

    Returns:
        the list of all the detectors found.
    """
    # Build the correct stabilizer lists
    left_boundary_stabilizers: list[BoundaryStabilizer] = []
    left_boundary_indices_map: list[int] = []
    for i, stabilizer in enumerate(left_flows.creation):
        if not stabilizer.has_anticommuting_operations:
            left_boundary_stabilizers.append(
                stabilizer.with_measurement_offset(
                    -right_flows.total_number_of_measurements
                )
            )
            left_boundary_indices_map.append(i)

    right_boundary_stabilizers: list[BoundaryStabilizer] = []
    right_boundary_indices_map: list[int] = []
    for i, stabilizer in enumerate(right_flows.destruction):
        if not stabilizer.has_anticommuting_operations:
            right_boundary_stabilizers.append(stabilizer)
            right_boundary_indices_map.append(i)

    # Check that there is at least a hope that a cover exist
    if len(left_boundary_stabilizers) == 0 or len(right_boundary_stabilizers) == 0:
        return []
    if len(left_boundary_stabilizers) == 1 and len(right_boundary_stabilizers) == 1:
        return []

    # Try to find a cover composed of measurements from the right flows that will
    # cancel the stabilizer propagated from one reset in the left flows.
    forward_detectors, left_reduced_indices_to_remove = (
        _match_boundary_stabilizers_by_disjoint_cover(
            left_boundary_stabilizers,
            right_boundary_stabilizers,
            qubit_coordinates,
            target_is_creation=True,
        )
    )
    # Remove all the left flows that have been matched with a cover. Both the actual flow
    # and the temporary list created above should be updated.
    for i in sorted(left_reduced_indices_to_remove, reverse=True):
        left_boundary_stabilizers.pop(i)
        left_flows.remove_creation(left_boundary_indices_map[i])

    # Try to find a cover composed of resets from the left flows that will cancel the
    # stabilizer propagated backward from one measurement in the right flows.
    backward_detectors, right_reduced_indices_to_remove = (
        _match_boundary_stabilizers_by_disjoint_cover(
            right_boundary_stabilizers,
            left_boundary_stabilizers,
            qubit_coordinates,
            target_is_creation=False,
        )
    )
    # Remove all the right flows that have been matched with a cover. Both the actual flow
    # and the temporary list created above should be updated.
    for i in sorted(right_reduced_indices_to_remove, reverse=True):
        right_boundary_stabilizers.pop(i)
        right_flows.remove_destruction(right_boundary_indices_map[i])

    # Return all the detectors that have been found.
    return forward_detectors + backward_detectors
