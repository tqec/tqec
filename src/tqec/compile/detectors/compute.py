import json
from typing import Sequence

import numpy
import numpy.typing as npt
import stim
from tqecd.flow import build_flows_from_fragments
from tqecd.fragment import Fragment
from tqecd.match import (
    MatchedDetector,
    match_boundary_stabilizers,
    match_detectors_within_fragment,
)

from tqec.circuit.coordinates import StimCoordinates
from tqec.circuit.generation import generate_circuit_from_instantiation
from tqec.circuit.measurement import Measurement, get_measurements_from_circuit
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit, relabel_circuits_qubit_indices
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.detector import Detector
from tqec.exceptions import TQECException
from tqec.plaquette.plaquette import Plaquettes
from tqec.position import Displacement, Position2D
from tqec.templates.indices.base import Template
from tqec.templates.indices.display import (
    get_template_representation_from_instantiation,
)
from tqec.templates.indices.subtemplates import (
    SubTemplateType,
    get_spatially_distinct_3d_subtemplates,
)


def _get_measurement_offset_mapping(circuit: stim.Circuit) -> dict[int, Measurement]:
    """Get a mapping from measurement offsets as used and returned by the
    package `tqecd.detectors` to a `Measurement` instance.

    This function returns the mapping from negative offsets that are
    supposed to each represent a unique measurement in the circuit to
    `Measurement` instances, that serve the same purpose but use a different
    encoding.

    Note:
        As a sanity check, the user of this function is encouraged to check
        if the qubits in each `Measurement` instances returned as values of
        the mapping corresponds to the expected qubit.

    Args:
        circuit: the circuit to create the mapping for.

    Returns:
        a mapping from record offset to :class:`Measurement` for all the
        measurements appearing in the provided `circuit`.
    """
    return {
        -i - 1: m
        for i, m in enumerate(reversed(get_measurements_from_circuit(circuit)))
    }


def _matched_detectors_to_detectors(
    detectors: list[MatchedDetector],
    measurements_by_offset: dict[int, Measurement],
) -> list[Detector]:
    """Transform :class:`MatchedDetector` instances into `Detector` ones.

    Args:
        detectors: list of detectors to translate.
        measurements_by_offset: map from measurement record offsets that are used
            in the provided `detectors` to :class:`Measurement` instances
            using a spatially-local representation of measurements.

    Returns:
        :class:`Detector` instances representing the same detectors as the
        provided `detectors`.
    """
    ret: list[Detector] = []
    for d in detectors:
        measurements: list[Measurement] = []
        for m in d.measurements:
            measurements.append(measurements_by_offset[m.offset])
        x, y, t = d.coords
        ret.append(Detector(frozenset(measurements), StimCoordinates(x, y, t)))
    return ret


def _center_plaquette_syndrome_qubits(
    subtemplate: SubTemplateType, plaquettes: Plaquettes, increments: Displacement
) -> list[GridQubit]:
    """Return a collection of qubits that are used as syndrome qubits by the
    central plaquette of the provided `subtemplate`.

    The qubits are returned in the sub-template coordinates (i.e., origin at
    top-left corner of the provided `subtemplate`).

    Args:
        subtemplate: 2-dimensional array representing the sub-template we are
            interested in.
        plaquettes: a collection of plaquettes that will be used to generate a
            circuit from the provided `subtemplate`.
        increments: spatial increments between each `Plaquette` origin.

    Returns:
        a collection of qubits that are used as syndrome qubits by the central
        plaquette. Returns an empty collection if the central plaquette has the
        index `0`.
    """
    # Subtemplates are expected to have a shape of (2*r+1, 2*r+1), so `r` can
    # be recovered by computing `(2*r+1) // 2 == r`.
    r = subtemplate.shape[0] // 2
    central_plaquette_index = int(subtemplate[r, r])

    if central_plaquette_index == 0:
        return []

    central_plaquette = plaquettes[central_plaquette_index]
    origin = central_plaquette.origin
    offset = Displacement(r * increments.x + origin.x, r * increments.y + origin.y)
    return [q + offset for q in central_plaquette.qubits.syndrome_qubits]


def _filter_detectors(
    detectors: list[Detector],
    subtemplates: Sequence[SubTemplateType],
    plaquettes: Sequence[Plaquettes],
    increments: Displacement,
) -> frozenset[Detector]:
    """Filter detectors that do not involve at least one measurement on a
    syndrome qubit of the central plaquette, in the last round.

    Warning:
        This function assumes that there is exactly one measurement on each
        syndrome qubit per round. That means that if a syndrome qubit is not
        measured, or if it is measured twice during the same round, this function
        will return wrong results.
        For the moment, this assumption is verified for all the plaquettes we are
        using, but this restriction should be kept in mind in case a future
        plaquette does not check this condition.

    Args:
        detectors: list of detectors to filter.
        subtemplates: subtemplate on which the detectors have been computed. Only
            the last time step (`subtemplates[-1]`) is used by this function.
        plaquettes: plaquettes on which the detectors have been computed. Only
            the last time step (`plaquettes[-1]`) is used by this function.
        increments: increment between two neighbouring plaquette origins.

    Returns:
        a filtered sequence of detectors. All the returned detectors are from
        the provided `detectors` (i.e., this function does not create or combine
        detectors).
    """
    # First, we want the detectors to be composed of at least one measurement
    # involving one of the syndrome qubits of the central plaquette in the last
    # timestep.
    central_syndrome_qubits_measurements = frozenset(
        # Assumes that syndrome qubits are only measured once per round, which
        # seems reasonable. But still, this is an important assumption.
        Measurement(q, -1)
        for q in _center_plaquette_syndrome_qubits(
            subtemplates[-1], plaquettes[-1], increments
        )
    )
    filtered_detectors = [
        d
        for d in detectors
        if d.measurements.intersection(central_syndrome_qubits_measurements)
    ]
    return frozenset(filtered_detectors)


def _compute_detectors_at_end_of_situation(
    subtemplates: Sequence[SubTemplateType],
    plaquettes: Sequence[Plaquettes],
    increments: Displacement,
) -> frozenset[Detector]:
    if len(plaquettes) != len(subtemplates):
        raise TQECException(
            "Unsupported input: you should provide as many subtemplates as "
            "there are plaquettes."
        )
    # Note: if the center plaquette of the last entry of `subtemplates` does not
    #       contain any measurement, then we can be sure that there is no
    #       detectors here, so early return.
    radius = subtemplates[-1].shape[0] // 2
    center_plaquette_index = subtemplates[-1][radius, radius]
    if center_plaquette_index == 0:
        return frozenset()
    center_plaquette = plaquettes[-1][center_plaquette_index]
    if center_plaquette.num_measurements == 0:
        return frozenset()

    # Note: if there is more than 1 time slice, remove any initial time slice
    #       that is empty.
    while len(subtemplates) > 1 and numpy.all(subtemplates[0] == 0):
        assert len(plaquettes) > 1  # make type checkers happy
        subtemplates = subtemplates[1:]
        plaquettes = plaquettes[1:]

    # Build subcircuit for each Plaquettes layer
    subcircuits: list[ScheduledCircuit] = []
    for subtemplate, plaqs in zip(subtemplates, plaquettes):
        subcircuit = generate_circuit_from_instantiation(subtemplate, plaqs, increments)
        subcircuits.append(subcircuit)
    # Extract the global qubit map from the generated sub-circuits, relabeling
    # qubits if needed.
    subcircuits, global_qubit_map = relabel_circuits_qubit_indices(subcircuits)
    # Get the stim.Circuit instances. We do not need the coordinates here
    # because we have already computed the global qubit map.
    coordless_subcircuits = [
        sc.get_circuit(include_qubit_coords=False) for sc in subcircuits
    ]
    # Get the full stim.Circuit to compute a measurement records offset map and
    # filter out detectors at the end.
    complete_circuit = global_qubit_map.to_circuit()
    for coordless_subcircuit in coordless_subcircuits[:-1]:
        complete_circuit += coordless_subcircuit
        complete_circuit.append("TICK", [], [])
    complete_circuit += coordless_subcircuits[-1]

    # Use tqecd.detectors module to match the detectors. Note that, for
    # the moment, only the last two time slices are taken into account.
    coordinates_by_index = {
        i: (float(q.x), float(q.y)) for i, q in global_qubit_map.items()
    }
    fragments = [Fragment(circ) for circ in coordless_subcircuits]
    flows = build_flows_from_fragments(fragments)
    matched_detectors = match_detectors_within_fragment(flows[-1], coordinates_by_index)
    if len(flows) == 2:
        matched_detectors.extend(
            match_boundary_stabilizers(flows[-2], flows[-1], coordinates_by_index)
        )
    # Note that the matched detectors do not have a time coordinate yet. Because
    # all the matched detectors belong to the last flow, the time coordinate can
    # just be "0". Simply add that to all detectors.
    matched_detectors = [d.with_time_coordinate(0) for d in matched_detectors]

    # Get the detectors as Detector instances instead of the
    # `tqecd.MatchedDetector` class.
    measurements_by_offset = _get_measurement_offset_mapping(complete_circuit)
    detectors = _matched_detectors_to_detectors(
        matched_detectors, measurements_by_offset
    )

    # Filter out detectors and return the left ones.
    return _filter_detectors(detectors, subtemplates, plaquettes, increments)


def _get_database_access_exception(
    subtemplates: Sequence[SubTemplateType],
    plaquettes_by_timestep: Sequence[Plaquettes],
) -> TQECException:
    return TQECException(
        "Failed to retrieve a situation from the provided database but "
        "only_use_database was True. Failing instead of computing "
        "automatically detectors. You might want to populate the "
        "database with the missing situation before re-calling this "
        "method. Description of the situation:\n"
        "Subtemplates and plaquettes (by decreasing time, the first "
        "displayed subtemplate is for the last timeslice):\n"
        + ("\n" + "-" * 40 + "\n").join(
            "\n".join(
                (
                    "Subtemplate:",
                    get_template_representation_from_instantiation(subtemplate),
                    "Plaquettes:",
                    json.dumps(plaquettes.to_name_dict()),
                )
            )
            for subtemplate, plaquettes in zip(subtemplates, plaquettes_by_timestep)
        )
    )


def compute_detectors_at_end_of_situation(
    subtemplates: Sequence[SubTemplateType],
    plaquettes_by_timestep: Sequence[Plaquettes],
    increments: Displacement,
    database: DetectorDatabase | None = None,
    only_use_database: bool = False,
) -> frozenset[Detector]:
    """Returns detectors that should be added at the end of the provided
    situation.

    Args:
        subtemplates: a sequence of sub-template(s), each entry consisting of
            a square 2-dimensional array of integers with odd-length sides
            representing the arrangement of plaquettes in a subtemplate.
        plaquettes_at_timestep: a sequence of collection of plaquettes each
            representing one QEC round.
        increments: spatial increments between each `Plaquette` origin.
        database: existing database of detectors that is used to avoid computing
            detectors if the database already contains them. If provided, this
            function guarantees that the database will contain the provided
            situation when returning (i.e., either it already contained the
            situation or it has been updated **in-place** with the computed
            detectors). If the database is frozen and a new situation is
            encountered, an exception will be thrown when trying to mutate the
            database. Default to `None` which result in not using any kind of
            database and unconditionally performing the detector computation.
        only_use_database: if True, only detectors from the database will be
            used. An error will be raised if a situation that is not registered
            in the database is encountered or if the database is not provided.
            Default to False.

    Returns:
        all the detectors that can be appended at the end of the circuit
        represented by the provided `subtemplates` and `plaquettes_at_timestep`.

    Raises:
        TQECException: if `len(subtemplates) != len(plaquettes_at_timestep)`.
    """

    # Try to recover the result from the database.
    if database is not None:
        detectors = database.get_detectors(subtemplates, plaquettes_by_timestep)
        # If not found and only detectors from the database should be used, this
        # is an error.
        if detectors is None and only_use_database:
            raise _get_database_access_exception(subtemplates, plaquettes_by_timestep)
        # Else, if not found but we are allowed to compute detectors, compute
        # and store in database.
        elif detectors is None:
            detectors = _compute_detectors_at_end_of_situation(
                subtemplates, plaquettes_by_timestep, increments
            )
            database.add_situation(subtemplates, plaquettes_by_timestep, detectors)
    # If database is None
    else:
        if only_use_database:
            raise _get_database_access_exception(subtemplates, plaquettes_by_timestep)
        detectors = _compute_detectors_at_end_of_situation(
            subtemplates, plaquettes_by_timestep, increments
        )

    # `subtemplate.shape` should be `(2 * radius + 1, 2 * radius + 1)` so we can
    # recover the radius with the below expression.
    radius = subtemplates[0].shape[0] // 2

    # We have a coordinate system change to apply to `detectors`.
    # `detectors` is using a coordinate system with the origin at the
    # top-left corner of the current sub-template, but we need to return
    # detectors that use the central plaquette origin as their coordinate system
    # origin.
    shift_x, shift_y = -radius * increments.x, -radius * increments.y

    return frozenset(d.offset_spatially_by(shift_x, shift_y) for d in detectors)


def _get_or_default(
    array: npt.NDArray[numpy.int_], slices: Sequence[tuple[int, int]], default: int = 0
) -> npt.NDArray[numpy.int_]:
    """Get slices of a `numpy` array, returning the provided `default` value
    for out-of-bound accesses.

    Args:
        array: `numpy` array to recover values from.
        slices: a sequence of tuples `(start, stop)` representing the slice that
            should be returned for the corresponding array axis. The first slice
            indexes elements on `axis=0`, the second on `axis=1`, ...
        default: value to use when indices from the provided slices are
            out-of-bound for the provided `array`. Defaults to 0.

    Raises:
        TQECException: if any of the provided slice has `start > stop`.
        TQECException: if the number of provided slices does not exactly match
            the number of dimensions of the provided array.

    Returns:
        `array[slices[0][0]:slices[0][1], ..., slices[-1][0]:slices[-1][1]]`,
        with any out-of-bounds index associated to the provided `default` value.
    """
    if any(start > stop for start, stop in slices):
        raise TQECException("The provided slices should be non-empty.")
    if len(slices) != len(array.shape):
        raise TQECException(
            f"Expected one slice per array dimension. Got {len(slices)} slices "
            f"but {len(array.shape)} dimensions to the provided array."
        )
    slice_shape = tuple(stop - start for start, stop in slices)
    ret = numpy.full(slice_shape, fill_value=default, dtype=numpy.int_)

    # Now, fill ret with entries from the provided array. We should make sure that
    # we do not try to access elements from `array` that do not exist (out of
    # bounds).
    ret_slices: list[slice] = []
    array_slices: list[slice] = []
    for (start_slice, stop_slice), array_bound in zip(slices, array.shape):
        start_array, stop_array = 0, array_bound
        if stop_slice <= start_array or start_slice >= stop_array:
            # Nothing to take from `array`, so append an empty slice for this
            # dimension.
            ret_slices.append(slice(0, 0))
            array_slices.append(slice(0, 0))
        elif start_array <= start_slice <= stop_slice <= stop_array:
            # The slice only contains valid indices for the array.
            ret_slices.append(slice(0, stop_slice - start_slice))
            array_slices.append(slice(start_slice, stop_slice))
        elif start_array < stop_slice <= stop_array:
            # The slice start is out of bound, but not the end.
            ret_slices.append(
                slice(start_array - start_slice, stop_slice - start_slice)
            )
            array_slices.append(slice(start_array, stop_slice))
        else:
            # The slice start is in bounds, but the end is not.
            ret_slices.append(slice(0, stop_array - start_slice))
            array_slices.append(slice(start_slice, stop_array))

    ret[tuple(ret_slices)] = array[tuple(array_slices)]
    return ret


def _compute_superimposed_template_instantiations(
    templates: Sequence[Template], k: int
) -> list[npt.NDArray[numpy.int_]]:
    """Compute the instantiation of all the provided `templates`, making sure
    that they are aligned with the last provided one.

    When instantiating multiple templates that are supposed to be stacked up on
    top of each other (i.e., executed one after the other) we might be
    confronted with several edge cases:

    - what if the templates do not have the same shape?
    - what if the templates do not have the same origin?

    In our specific case of computing detectors, we always focus on the top-most
    (i.e., last executed, last entry of the provided `templates`) template because
    this is the template that we are searching detectors in. That means that we
    want to instantiate :class:`Template` instances with potentially different
    shapes and origins and be sure that they are all aligned with the top-most
    :class:`Template` instance.

    This function ensures exactly this. It does that by instantiating all the
    provided templates and cutting all the obtained instantiations to the
    coordinates where the last provided template is defined.

    Args:
        templates: instances representing templates that will be instantiated
            and cut to the coordinates where `templates[-1]` is defined.
        k: scaling parameter used to instantiate `templates`.

    Returns:
        a list of template instantiation that all have the same shape and the
        same origin, meaning that in the final circuit `ret[i][x, y]` represent
        indices of plaquettes that will be stacked up (in time) for all `i` and
        any `x` and `y`.
    """
    origins = [t.instantiation_origin(k) for t in templates]
    instantiations = [t.instantiate(k) for t in templates]

    top_left = origins[-1]
    n, m = instantiations[-1].shape
    bottom_right = Position2D(top_left.x + m, top_left.y + n)

    # Get the correct instantiations
    ret: list[npt.NDArray[numpy.int_]] = []
    for inst_origin, instantiation in zip(origins, instantiations):
        ret.append(
            _get_or_default(
                instantiation,
                slices=[
                    (top_left.y - inst_origin.y, bottom_right.y - inst_origin.y),
                    (top_left.x - inst_origin.x, bottom_right.x - inst_origin.x),
                ],
                default=0,
            )
        )
    return ret


def compute_detectors_for_fixed_radius(
    templates: Sequence[Template],
    k: int,
    plaquettes: Sequence[Plaquettes],
    fixed_subtemplate_radius: int = 2,
    database: DetectorDatabase | None = None,
    only_use_database: bool = False,
) -> list[Detector]:
    """Returns detectors that should be added at the end of the circuit that
    would be obtained from the provided `template_at_timestep` and
    `plaquettes_at_timestep`.

    Args:
        templates: a sequence containing `t` :class:`Template` instance(s), each
            representing one QEC round.
        k: scaling factor to consider in order to instantiate the provided
            template.
        plaquettes: a sequence containing `t` collection(s) of plaquettes each
            representing one QEC round.
        fixed_subtemplate_radius: Manhattan radius to consider when splitting the
            provided `template` into sub-templates. Should be large enough so
            that flows cancelling each other to form a detector are strictly
            contained in the sub-template and cannot escape from it (which is
            mostly equivalent to say that flows should not interact with qubits
            on the border of the sub-templates).
        database: existing database of detectors that is used to avoid computing
            detectors if the database already contains them. If provided, this
            function guarantees that the database will contain the provided
            situation when returning (i.e., either it already contained the
            situation or it has been updated **in-place** with the computed
            detectors). Default to `None` which result in not using any kind of
            database and unconditionally performing the detector computation.
        only_use_database: if True, only detectors from the database will be
            used. An error will be raised if a situation that is not registered
            in the database is encountered. Default to False.

    Returns:
        a collection of detectors that should be added at the end of the circuit
        that would be obtained from the provided `templates` and `plaquettes`.
    """
    all_increments = frozenset(t.get_increments() for t in templates)
    if len(all_increments) != 1:
        raise TQECException(
            "Expected all the provided templates to have the same increments. "
            f"Found the following different increments: {all_increments}."
        )
    increments = next(iter(all_increments))

    if len(templates) != len(plaquettes):
        raise TQECException(
            "Expecting the same number of entries in templates and plaquettes."
        )

    template_instantiations = _compute_superimposed_template_instantiations(
        templates, k
    )
    unique_3d_subtemplates = get_spatially_distinct_3d_subtemplates(
        template_instantiations,
        manhattan_radius=fixed_subtemplate_radius,
        avoid_zero_plaquettes=True,
    )

    # Each detector in detectors_by_subtemplate is using a coordinate system
    # centered on the central plaquette origin.
    detectors_by_subtemplate: dict[tuple[int, ...], frozenset[Detector]] = {
        indices: compute_detectors_at_end_of_situation(
            [s3d[:, :, i] for i in range(s3d.shape[2])],
            plaquettes,
            increments,
            database,
            only_use_database,
        )
        for indices, s3d in unique_3d_subtemplates.subtemplates.items()
    }
    # We know for sure that detectors in each subtemplate all involve a measurement
    # on at least one syndrome qubit of the central plaquette. That means that
    # detectors computed here are unique and we do not have to check for
    # duplicates.
    # Also, the last timestep template origin might not be (0, 0), so we have
    # to shift detectors accordingly.
    last_template_origin = templates[-1].instantiation_origin(k)
    detectors: list[Detector] = []
    for i, row in enumerate(unique_3d_subtemplates.subtemplate_indices):
        for j, subtemplate_indices in enumerate(row):
            if numpy.all(subtemplate_indices == 0):
                continue
            for d in detectors_by_subtemplate[tuple(subtemplate_indices)]:
                detectors.append(
                    d.offset_spatially_by(
                        (j + last_template_origin.x) * increments.x,
                        (i + last_template_origin.y) * increments.y,
                    )
                )

    return detectors
