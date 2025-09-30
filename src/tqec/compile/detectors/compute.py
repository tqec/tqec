import json
from collections.abc import Sequence
from multiprocessing import Pool, cpu_count

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

from tqec.circuit.measurement import Measurement, get_measurements_from_circuit
from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit, relabel_circuits_qubit_indices
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.detectors.detector import Detector
from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import Template
from tqec.templates.display import get_template_representation_from_instantiation
from tqec.templates.subtemplates import (
    SubTemplateType,
    get_spatially_distinct_3d_subtemplates,
)
from tqec.utils.array import to2dlist
from tqec.utils.coordinates import StimCoordinates
from tqec.utils.exceptions import TQECError
from tqec.utils.position import PlaquettePosition2D, Shift2D


def _get_measurement_offset_mapping(circuit: stim.Circuit) -> dict[int, Measurement]:
    """Get a mapping from measurement offsets to a :class:`.Measurement` instance.

    The measurement offsets used as keys in the returned mapping are in accordance with the
    ``tqecd.detectors`` external package.

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
    return {-i - 1: m for i, m in enumerate(reversed(get_measurements_from_circuit(circuit)))}


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
        measurements: list[Measurement] = [measurements_by_offset[m.offset] for m in d.measurements]
        x, y, t = d.coords
        ret.append(Detector(frozenset(measurements), StimCoordinates(x, y, t)))
    return ret


def _center_plaquette_syndrome_qubits(
    subtemplate: SubTemplateType, plaquettes: Plaquettes, increments: Shift2D
) -> list[GridQubit]:
    """Return the syndrome qubits used by the central plaquette of the provided ``subtemplate``.

    The qubits are returned in the sub-template coordinates (i.e., origin at top-left corner of the
    provided `subtemplate`).

    Note:
        This function only returns a subset of the syndrome qubits. This is
        because, for some plaquettes (e.g., extended stabilizer measurement),
        some corner qubits are syndrome qubits, but are shared by 4 plaquettes.
        For this reason, each plaquette "owns" its top-left qubit. Following
        this rule, there are a few cases where a data-qubit is owned by nobody,
        hence a few exceptions to the above rule are added.

    Warning:
        If the provided ``subtemplate`` has been obtained from a manhattan radius
        ``r == 0`` (i.e., no neighbouring plaquette is taken into account), only
        the top-left data-qubit is owned by the plaquette, and no exception come
        into play.

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

    # In the following, "X" is a qubit that "belongs" to the plaquette drawn
    # using "=" and "|", "O" is a qubit that does not, and plaquette(s) drawn
    # using "~" and "'" are representing empty plaquettes. Numbers in the center
    # of empty plaquettes correspond to the case applied to justify the absence
    # of owner.

    # Case 1, General case, always valid:
    # X ===== O
    # |       |
    # |   X   |
    # |       |
    # O ===== O
    considered_syndrome_qubits = {GridQubit(0, 0), GridQubit(-1, -1)}
    # Case 2, when the top-right qubit should be added because no plaquette on
    # the left to own it.
    # X ===== X ~~~~~ O
    # |       |       '
    # |   X   |   1   '
    # |       |       '
    # O ===== O ~~~~~ O
    if r != 0 and subtemplate[r, r + 1] == 0:
        considered_syndrome_qubits |= {GridQubit(1, -1)}
    # When the bottom-left qubit should be added because no plaquette on the
    # bottom and bottom-left to own it.
    #         X ===== O
    #         |       |
    #         |   X   |
    #         |       |
    # O ~~~~~ X ===== O
    # '       '       '
    # '   2   '   1   '
    # '       '       '
    # O ~~~~~ O ~~~~~ O
    if r != 0 and (subtemplate[r + 1, r - 1] == subtemplate[r + 1, r] == 0):
        considered_syndrome_qubits |= {GridQubit(-1, 1)}
    # When the bottom-right qubit should be added because no plaquette on the
    # bottom, bottom-right and right to own it.
    # X ===== O ~~~~~ O
    # |       |       '
    # |   X   |   3   '
    # |       |       '
    # O ===== X ~~~~~ O
    # '       '       '
    # '   2   '   1   '
    # '       '       '
    # O ~~~~~ O ~~~~~ O
    if r != 0 and (
        subtemplate[r + 1, r - 1] == subtemplate[r + 1, r] == subtemplate[r, r + 1] == 0
    ):
        considered_syndrome_qubits |= {GridQubit(1, 1)}

    central_plaquette = plaquettes[central_plaquette_index]
    origin = central_plaquette.origin
    offset = Shift2D(r * increments.x + origin.x, r * increments.y + origin.y)
    return [
        q + offset
        for q in central_plaquette.qubits.syndrome_qubits
        if q in considered_syndrome_qubits
    ]


def _best_effort_filter_detectors(
    detectors: list[Detector],
    subtemplates: Sequence[SubTemplateType],
    plaquettes: Sequence[Plaquettes],
    increments: Shift2D,
) -> frozenset[Detector]:
    """Filter detectors using a best-effort strategy.

    This function filters out detectors that do not involve at least one measurement on a syndrome
    qubit of the central plaquette in the last round. Such a filtering is voluntarily not too
    strict, as the goal is to reduce the number of detectors that should be considered, but a more
    robust filter will be applied later in the pipeline. So this function implements a good-enough
    filtering that is not perfect, but that is at least guaranteed not to remove detectors that
    should not be removed.

    Warning:
        This function assumes that there is exactly one measurement on each
        syndrome qubit per round. That means that if a syndrome qubit is not
        measured, or if it is measured twice during the same round, this function
        will return wrong results.
        For the moment, this assumption is verified for all the plaquettes we are
        using, but this restriction should be kept in mind in case a future
        plaquette does not check this condition.

    Warning:
        This function tries as much as possible to filter the maximum number of
        detectors for the provided ``subtemplates`` and ``plaquettes``. For the
        moment, this filtering is not perfect and detectors might end up
        duplicated on several combos of ``subtemplates`` and ``plaquettes``.

        That is not a problem as long as the number of duplicated detectors is
        relatively low and a second more robust filter based on deduplication
        via ``set`` is in place.

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
        for q in _center_plaquette_syndrome_qubits(subtemplates[-1], plaquettes[-1], increments)
    )
    filtered_detectors = [
        d for d in detectors if d.measurements.intersection(central_syndrome_qubits_measurements)
    ]
    return frozenset(filtered_detectors)


def _compute_detectors_at_end_of_situation(
    subtemplates: Sequence[SubTemplateType],
    plaquettes: Sequence[Plaquettes],
    increments: Shift2D,
) -> frozenset[Detector]:
    if len(plaquettes) != len(subtemplates):
        raise TQECError(
            "Unsupported input: you should provide as many subtemplates as there are plaquettes."
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
    # that is trivially empty. This is a faster version of the next while loop,
    # but this might not catch all empty circuits (e.g., those that have an
    # explicit plaquette, that turns out to be empty).
    while len(subtemplates) > 1 and numpy.all(subtemplates[0] == 0):
        assert len(plaquettes) > 1  # make type checkers happy
        subtemplates = subtemplates[1:]
        plaquettes = plaquettes[1:]

    # Note: if there is more than 1 time slice, remove any initial time slice
    # that is empty. Same as above, but without any false negative and less
    # efficient.
    current_circuit = generate_circuit_from_instantiation(
        subtemplates[0], plaquettes[0], increments
    )
    while len(subtemplates) > 1 and current_circuit.is_empty():
        assert len(plaquettes) > 1  # make type checkers happy
        subtemplates = subtemplates[1:]
        plaquettes = plaquettes[1:]
        current_circuit = generate_circuit_from_instantiation(
            subtemplates[0], plaquettes[0], increments
        )
    # Build subcircuit for each Plaquettes layer
    subcircuits: list[ScheduledCircuit] = [current_circuit]
    for subtemplate, plaqs in zip(subtemplates[1:], plaquettes[1:]):
        subcircuit = generate_circuit_from_instantiation(subtemplate, plaqs, increments)
        subcircuits.append(subcircuit)
    # Extract the global qubit map from the generated sub-circuits, relabeling
    # qubits if needed.
    subcircuits, global_qubit_map = relabel_circuits_qubit_indices(subcircuits)
    # Get the stim.Circuit instances. We do not need the coordinates here
    # because we have already computed the global qubit map.
    coordless_subcircuits = [sc.get_circuit(include_qubit_coords=False) for sc in subcircuits]
    # Get the full stim.Circuit to compute a measurement records offset map and
    # filter out detectors at the end.
    complete_circuit = global_qubit_map.to_circuit()
    for coordless_subcircuit in coordless_subcircuits[:-1]:
        complete_circuit += coordless_subcircuit
        complete_circuit.append("TICK", [], [])
    complete_circuit += coordless_subcircuits[-1]

    # Use tqecd.detectors module to match the detectors. Note that, for
    # the moment, only the last two time slices are taken into account.
    coordinates_by_index = {i: (float(q.x), float(q.y)) for i, q in global_qubit_map.items()}
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
    detectors = _matched_detectors_to_detectors(matched_detectors, measurements_by_offset)

    # Filter out detectors and return the left ones.
    return _best_effort_filter_detectors(detectors, subtemplates, plaquettes, increments)


def _get_database_access_exception(
    subtemplates: Sequence[SubTemplateType],
    plaquettes_by_timestep: Sequence[Plaquettes],
) -> TQECError:
    return TQECError(
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
    increments: Shift2D,
    database: DetectorDatabase | None = None,
    only_use_database: bool = False,
    parallel_process_count: int = 1,
) -> frozenset[Detector]:
    """Return detectors that should be added at the end of the provided situation.

    Args:
        subtemplates: a sequence of sub-template(s), each entry consisting of
            a square 2-dimensional array of integers with odd-length sides
            representing the arrangement of plaquettes in a subtemplate.
        plaquettes_by_timestep: a sequence of collection of plaquettes each
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
        only_use_database: if ``True``, only detectors from the database will be
            used. An error will be raised if a situation that is not registered
            in the database is encountered or if the database is not provided.
            Default to ``False``.
        parallel_process_count: number of processes to use for parallel processing.
            1 for sequential processing, >1 for parallel processing using
            ``parallel_process_count`` processes, and -1 for using all available
            CPU cores. Default to 1.

    Returns:
        all the detectors that can be appended at the end of the circuit
        represented by the provided `subtemplates` and `plaquettes_at_timestep`.

    Raises:
        TQECError: if `len(subtemplates) != len(plaquettes_at_timestep)`.

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

    # If parallel processing is not enabled, shift the detectors here.
    # Otherwise, wait until all child processes have finished computation.
    # In that case, update the database with the computed detectors in the parent process,
    # and then shift the detectors afterwards.
    if parallel_process_count == 1:
        detectors = _shift_detectors_to_center_of_subtemplate(detectors, subtemplates, increments)
    return detectors


def _shift_detectors_to_center_of_subtemplate(
    detectors: frozenset[Detector],
    subtemplates: Sequence[SubTemplateType],
    increments: Shift2D,
) -> frozenset[Detector]:
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
    """Get slices of an array, returning the provided ``default`` value for out-of-bound accesses.

    Args:
        array: `numpy` array to recover values from.
        slices: a sequence of tuples `(start, stop)` representing the slice that
            should be returned for the corresponding array axis. The first slice
            indexes elements on `axis=0`, the second on `axis=1`, ... The start
            is inclusive, the stop is exclusive.
        default: value to use when indices from the provided slices are
            out-of-bound for the provided `array`. Defaults to 0.

    Raises:
        TQECError: if any of the provided slice has `start > stop`.
        TQECError: if the number of provided slices does not exactly match
            the number of dimensions of the provided array.

    Returns:
        `array[slices[0][0]:slices[0][1], ..., slices[-1][0]:slices[-1][1]]`,
        with any out-of-bounds index associated to the provided `default` value.

    """
    if any(start > stop for start, stop in slices):
        raise TQECError("The provided slices should be non-empty.")
    if len(slices) != len(array.shape):
        raise TQECError(
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
        # There are 6 different cases:
        #      start_array                                   stop_array
        #           [--------------------------------------------[
        #
        # 1: [--[
        # 2:                                                        [--[
        # 3:    [------------------------------------------------------[
        # 4:    [---------------------[
        # 5:                                           [---------------[
        # 6:                   [--------------------------[

        # In cases 1 or 2, there is nothing to take from the array so append an
        # empty slice.
        if stop_slice <= start_array or start_slice >= stop_array:
            ret_slices.append(slice(0, 0))
            array_slices.append(slice(0, 0))
        # In case 3, the slice covers the array, so take the whole dimension of
        # the array.
        elif start_slice <= start_array and stop_array <= stop_slice:
            ret_slices.append(slice(start_array - start_slice, stop_array - start_slice))
            array_slices.append(slice(start_array, stop_array))
        # In case 4, only a part of the slice covers the array.
        elif start_slice <= start_array < stop_slice <= stop_array:
            ret_slices.append(slice(start_array - start_slice, stop_slice - start_slice))
            array_slices.append(slice(start_array, stop_slice))
        # In case 5, only a part of the slice covers the array.
        elif start_array <= start_slice < stop_array <= stop_slice:
            ret_slices.append(slice(0, stop_array - start_slice))
            array_slices.append(slice(start_slice, stop_array))
        # In case 6, the whole slice is within bounds, to use the whole slice.
        elif start_array <= start_slice <= stop_slice <= stop_array:
            ret_slices.append(slice(0, stop_slice - start_slice))
            array_slices.append(slice(start_slice, stop_slice))
        else:
            raise NotImplementedError(
                f"Trying to get the slice [{start_slice}, {stop_slice}[ from an "
                f"array of size {stop_array}. The case should be covered, but "
                "none of the conditions matched, which hints at a mistake "
                "somewhere."
            )

    ret[tuple(ret_slices)] = array[tuple(array_slices)]
    return ret


def _compute_superimposed_template_instantiations(
    templates: Sequence[Template], k: int
) -> list[npt.NDArray[numpy.int_]]:
    """Compute the instantiation of all the provided ``templates``, taking care of alignment.

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
    bottom_right = PlaquettePosition2D(top_left.x + m, top_left.y + n)

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


def _extract_subtemplates_from_s3d(
    s3d: npt.NDArray[numpy.int_],
) -> list[npt.NDArray[numpy.int_]]:
    """Extract 2D spatial subtemplates from a 3D array.

    This function takes a 3D array where the first two dimensions
    represent spatial coordinates and the third dimension represents time steps.
    It extracts a list of 2D spatial arrays, one for each time step.

    Args:
        s3d: 3D numpy array representation of sub-templates.

    Returns:
        List of 2D numpy arrays, one for each time step.

    """
    return [s3d[:, :, i] for i in range(s3d.shape[2])]


def _compute_detector_for_subtemplate(
    args: tuple[
        tuple[int, ...],  # indices
        npt.NDArray[numpy.int_],  # s3d
        Sequence[Plaquettes],  # plaquettes
        Shift2D,  # increments
        int,  # parallel_process_count
    ],
) -> tuple[tuple[int, ...], frozenset[Detector]]:
    """Wrap :func:`compute_detectors_at_end_of_situation` for parallel processing of detectors.

    Args:
        args: A tuple containing:
            - indices: Tuple of indices identifying the subtemplate
            - s3d: 3D numpy array representing the subtemplate
            - plaquettes: Sequence of plaquettes for each time slice
            - increments: Spatial increments between plaquette origins
            - only_use_database: Whether to only use the database

    Returns:
        A tuple containing the indices and the computed detectors

    """
    indices, s3d, plaquettes, increments, parallel_process_count = args
    return (
        indices,
        compute_detectors_at_end_of_situation(
            _extract_subtemplates_from_s3d(s3d),
            plaquettes,
            increments,
            # Currently, we do not find an efficient way to share the database between
            # multiple processes, so we just pass `None` here.
            database=None,
            only_use_database=False,
            parallel_process_count=parallel_process_count,
        ),
    )


def compute_detectors_for_fixed_radius(
    templates: Sequence[Template],
    k: int,
    plaquettes: Sequence[Plaquettes],
    fixed_subtemplate_radius: int = 2,
    database: DetectorDatabase | None = None,
    only_use_database: bool = False,
    parallel_process_count: int = 1,
) -> list[Detector]:
    """Compute and returns detectors from the provided computation description.

    This function computes the detectors that should be added at the end of the circuit that would
    be obtained from the provided ``template_at_timestep`` and ``plaquettes_at_timestep`` and
    returns them.

    Using a template + plaquette approach allows for efficient detector computation.

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
        only_use_database: if ``True``, only detectors from the database will be
            used. An error will be raised if a situation that is not registered
            in the database is encountered. Default to ``False``.
        parallel_process_count: number of processes to use for parallel processing.
            1 for sequential processing, >1 for parallel processing using
            ``parallel_process_count`` processes, and -1 for using all available
            CPU cores. Default to 1.

    Returns:
        a collection of detectors that should be added at the end of the circuit
        that would be obtained from the provided `templates` and `plaquettes`.

    """
    all_increments = frozenset(t.get_increments() for t in templates)
    if len(all_increments) != 1:
        raise TQECError(
            "Expected all the provided templates to have the same increments. "
            f"Found the following different increments: {all_increments}."
        )
    increments = next(iter(all_increments))

    if len(templates) != len(plaquettes):
        raise TQECError("Expecting the same number of entries in templates and plaquettes.")

    template_instantiations = _compute_superimposed_template_instantiations(templates, k)
    unique_3d_subtemplates = get_spatially_distinct_3d_subtemplates(
        template_instantiations, manhattan_radius=fixed_subtemplate_radius
    )

    # Each detector in detectors_by_subtemplate is using a coordinate system
    # centered on the central plaquette origin.
    detectors_by_subtemplate: dict[tuple[int, ...], frozenset[Detector]] = {}

    # Handle the special case of parallel_process_count == -1
    if parallel_process_count == -1:
        parallel_process_count = cpu_count()
    # If parallel_process_count > 1 we will enable parallel processing to
    # compute detectors in parallel.
    if parallel_process_count > 1:
        args_list = [
            (indices, s3d, plaquettes, increments, parallel_process_count)
            for indices, s3d in unique_3d_subtemplates.subtemplates.items()
        ]

        with Pool(processes=parallel_process_count) as pool:
            results = pool.map(_compute_detector_for_subtemplate, args_list)

        # After synchronizing all child processes, we get all computed detectors,
        # first we add them to database if it is provides, then we shift the coordinates of them
        for indices, detectors_set in results:
            subtemplates = _extract_subtemplates_from_s3d(
                unique_3d_subtemplates.subtemplates[indices]
            )
            if database is not None:
                database.add_situation(subtemplates, plaquettes, detectors_set)
            detectors_by_subtemplate[indices] = _shift_detectors_to_center_of_subtemplate(
                detectors_set, subtemplates, increments
            )

    # If parallel_process_count == 1, computing detectors sequentially
    elif parallel_process_count == 1:
        detectors_by_subtemplate = {
            indices: compute_detectors_at_end_of_situation(
                _extract_subtemplates_from_s3d(s3d),
                plaquettes,
                increments,
                database,
                only_use_database,
            )
            for indices, s3d in unique_3d_subtemplates.subtemplates.items()
        }
    # Else, invalid parallel_process_count
    else:
        raise TQECError(
            f"Invalid parallel_process_count: {parallel_process_count}. "
            "Expected a positive integer or -1 for using all available CPU cores."
        )

    # We know for sure that detectors in each subtemplate all involve a measurement
    # on at least one syndrome qubit of the central plaquette. That means that
    # detectors computed here are unique and we do not have to check for
    # duplicates.
    # Also, the last timestep template origin might not be (0, 0), so we have
    # to shift detectors accordingly.
    last_template_origin = templates[-1].instantiation_origin(k)
    detectors: list[Detector] = []
    # The below line is not strictly needed, but makes type checkers happy with
    # type inference. See https://numpy.org/doc/stable/reference/typing.html#d-arrays
    # for more information on why this should be done.
    subtemplate_indices_list: list[list[list[int]]] = [
        to2dlist(arr) for arr in unique_3d_subtemplates.subtemplate_indices
    ]
    for i, row in enumerate(subtemplate_indices_list):
        for j, subtemplate_indices in enumerate(row):
            if all(i == 0 for i in subtemplate_indices):
                continue
            detectors.extend(
                d.offset_spatially_by(
                    (j + last_template_origin.x) * increments.x,
                    (i + last_template_origin.y) * increments.y,
                )
                for d in detectors_by_subtemplate[tuple(subtemplate_indices)]
            )
    # Second filter, here to catch the duplicated detectors that were not
    # filtered by the _best_effort_filter_detectors function.
    detectors = list(set(detectors))
    return detectors
