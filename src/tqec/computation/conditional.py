"""Correlation surfaces of computations that contain conditional cubes.

A computation with conditional cubes resolves to a different static computation for each
assignment of the runtime condition bits, so its correlation surfaces are branch-dependent.
They are compiled from user-provided *partial* correlation surfaces, exactly like the
``condition`` attribute of a conditional cube: the partial surface pins the Pauli content of
the observable, and the completion into a full correlation surface is deferred.

The compiled artifact, :class:`ConditionalCorrelationSurface`, is scalable to any number of
conditional cubes: it stores a generating set of correlation surfaces satisfying the closure
of every *static* leaf, together with a small preprocessed GF(2) linear system. Once the
relevant condition bits are known at runtime, :meth:`ConditionalCorrelationSurface.resolve`
selects the closure row of each conditional cube by its resolved branch, solves the system by
Gaussian elimination over the (already reduced) kernel coordinates, and XORs the selected
generators. No step enumerates branch assignments, so the compile- and runtime costs are
polynomial in the graph size and the number of conditional cubes.

Two completion entry points share the machinery:

- **Observables** (:func:`complete_observable_surfaces`): completed on the whole graph. The
  external identity of the observable, i.e. its Pauli operators at the ports and, when
  non-deterministic observables are requested, its coin signature at the initialization
  leaves, is pinned at compile time so that every branch resolves to the same observable
  class.
- **Conditions** (:func:`complete_condition_surface`): the partial condition surface of a
  conditional cube completed on the strict past of the cube. The completion may terminate
  anticommuting on initialization leaves, contributing uniformly random logical *coins* to
  the parity, e.g. lattice surgery merge outcomes, and may dangle at the interfaces to the
  future, tracking the Pauli frame of the dangling logical operators. Anticommuting
  terminations on measurement-type leaves are never allowed: the records they would require
  do not exist.

Solvability is only certified at compile time for the spec (and pinned identity); whether a
valid completion exists under the branch assignment actually realized is discovered by
:meth:`ConditionalCorrelationSurface.resolve`, which raises a descriptive error on an
unsolvable branch. Conditional cubes carrying equal ``condition`` partial surfaces share one
classical bit: :meth:`ConditionalCorrelationSurface.resolve` validates that their resolved
values agree.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from tqec.computation.block_graph import (
    _PARTITION_ALONG_TIME_MIN_LEAF_CUBES,
    BlockGraph,
)
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import ConditionalCubeKind, Cube, StaticCubeKind
from tqec.utils.enums import Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

if TYPE_CHECKING:
    from tqec.interop.pyzx.positioned import PositionedZX


class ConditionalCubeConstraint(NamedTuple):
    """The runtime closure constraint of one conditional cube on a completed surface.

    ``rows[b]`` is the closure row selected when the cube's condition bit resolves to ``b``,
    as a pair ``(coefficients, target)``: ``coefficients`` is a bit mask over the kernel
    coordinates of the :class:`ConditionalCorrelationSurface` and ``target`` is the required
    parity. The resolved surface ``particular XOR kernel-combination`` satisfies the closure
    of the resolved branch exactly when the combination ``c`` obeys
    ``parity(coefficients & c) == target``.
    """

    position: Position3D
    rows: tuple[tuple[int, int], tuple[int, int]]


@dataclass(frozen=True)
class ConditionalCorrelationSurface:
    """Branch-dependent correlation surface as a generating set plus a GF(2) linear system.

    The surface of a resolved branch assignment is the XOR of :attr:`particular` with a
    combination of :attr:`kernel` elements solving the closure rows selected by the resolved
    condition bits (:attr:`constraints`). The generators satisfy the closure of every static
    leaf and pin the user-specified partial surface and, for observables, the external
    identity (ports and coins), so the runtime system only carries one row per conditional
    cube in scope.

    Attributes:
        generators: The generating set of correlation surfaces. Combinations are referenced
            by bit masks over the generator indices.
        particular: The bit mask of the reference combination: it satisfies the pinned rows
            (partial surface and identity) but not necessarily any branch closure.
        kernel: Bit masks of the combinations acting trivially on the pinned rows, reduced at
            compile time to at most one element per distinct closure/coin signature. The
            runtime system's coefficients live over these kernel coordinates.
        constraints: The closure constraint of each conditional cube the completion may touch,
            sorted by position.
        coin_rows: For each initialization leaf that the completion may terminate on
            anticommuting, the ``(position, coefficients, target)`` row classifying whether
            the resolved surface picks up that leaf's logical coin.
        bit_groups: Sets of conditional cube positions sharing one classical bit, i.e. cubes
            carrying equal ``condition`` partial surfaces. :meth:`resolve` validates that the
            provided values agree within each group.

    """

    generators: tuple[CorrelationSurface, ...]
    particular: int
    kernel: tuple[int, ...] = ()
    constraints: tuple[ConditionalCubeConstraint, ...] = ()
    coin_rows: tuple[tuple[Position3D, int, int], ...] = ()
    bit_groups: tuple[frozenset[Position3D], ...] = ()

    def __post_init__(self) -> None:
        num_generators = len(self.generators)
        if not 0 <= self.particular < 1 << num_generators:
            raise TQECError("The particular combination references unknown generators.")
        if any(not 0 < mask < 1 << num_generators for mask in self.kernel):
            raise TQECError("A kernel combination is empty or references unknown generators.")
        object.__setattr__(
            self, "constraints", tuple(sorted(self.constraints, key=lambda c: c.position))
        )
        constraint_positions = {constraint.position for constraint in self.constraints}
        groups = tuple(frozenset(group) for group in self.bit_groups)
        grouped: set[Position3D] = set()
        for group in groups:
            if not group <= constraint_positions:
                raise TQECError("A bit group references positions without a closure constraint.")
            if group & grouped:
                raise TQECError("The bit groups must be disjoint.")
            grouped |= group
        object.__setattr__(self, "bit_groups", tuple(sorted(groups, key=sorted)))

    @property
    def dependencies(self) -> frozenset[Position3D]:
        """The positions of the conditional cubes whose condition bits select the surface."""
        return frozenset(constraint.position for constraint in self.constraints)

    def _condition_bits(
        self, condition_values: Mapping[Position3D, bool | int] | bool | int
    ) -> list[int]:
        """Return the condition bit of each constraint, validating the bit groups."""
        if isinstance(condition_values, Mapping):
            bits = [
                int(bool(condition_values[constraint.position])) for constraint in self.constraints
            ]
        else:
            bits = [int(bool(condition_values))] * len(self.constraints)
        by_position = {constraint.position: bit for constraint, bit in zip(self.constraints, bits)}
        for group in self.bit_groups:
            if len({by_position[position] for position in group}) > 1:
                raise TQECError(
                    f"The conditional cubes at {sorted(group)} share one condition bit but "
                    "were given different condition values."
                )
        return bits

    def _solve(self, bits: Sequence[int]) -> int:
        """Solve the closure rows selected by the bits for a kernel-coefficient mask.

        Raises:
            TQECError: If the selected rows are inconsistent, i.e. the completion does not
                exist under this branch assignment.

        """
        width = len(self.kernel)
        # Gaussian elimination on the augmented rows (target bit above the coefficients).
        pivots: dict[int, int] = {}
        for constraint, bit in zip(self.constraints, bits):
            coefficients, target = constraint.rows[bit]
            row = coefficients | (target << width)
            while row & ((1 << width) - 1):
                lead = (row & ((1 << width) - 1)).bit_length() - 1
                if lead not in pivots:
                    pivots[lead] = row
                    break
                row ^= pivots[lead]
            else:
                if row:  # 0 == 1: inconsistent system
                    resolution = {
                        constraint.position: bit for constraint, bit in zip(self.constraints, bits)
                    }
                    raise TQECError(
                        "The conditional correlation surface has no valid resolution when "
                        f"the conditional cubes resolve to {resolution}."
                    )
        # Back-substitute with the free coefficients set to zero, sweeping ascending leads.
        solution = 0
        for lead in sorted(pivots):
            row = pivots[lead]
            value = ((row >> width) & 1) ^ (row & solution).bit_count() & 1
            solution |= value << lead
        return solution

    def resolve(
        self, condition_values: Mapping[Position3D, bool | int] | bool | int
    ) -> CorrelationSurface:
        """Return the correlation surface selected by the given condition values.

        Args:
            condition_values: the runtime value(s) of the conditions. If a single boolean (or
                integer) is provided, the condition bits of all the conditional cubes take
                that value. Otherwise, a mapping from the positions of the conditional cubes
                to their respective condition values must be provided, covering
                :attr:`dependencies`.

        Returns:
            The correlation surface of the selected branch: the XOR of :attr:`particular`
            with the kernel combination solving the selected closure rows.

        Raises:
            TQECError: If no valid completion exists under this branch assignment, or if the
                values disagree within a bit group.
            KeyError: if ``condition_values`` is a mapping and does not contain an entry for
                some position in :attr:`dependencies`.

        """
        coefficients = self._solve(self._condition_bits(condition_values))
        combination = self.particular
        for j, kernel_mask in enumerate(self.kernel):
            if (coefficients >> j) & 1:
                combination ^= kernel_mask
        surface = CorrelationSurface(frozenset())
        for i, generator in enumerate(self.generators):
            if (combination >> i) & 1:
                surface = surface ^ generator
        return surface

    def coins(
        self, condition_values: Mapping[Position3D, bool | int] | bool | int
    ) -> frozenset[Position3D]:
        """Return the coin positions of the resolution selected by the given condition values.

        The coins are the initialization leaf cubes on which the resolved surface terminates
        anticommuting, each contributing one uniformly random logical bit to the parity. The
        set is empty for deterministic observables, whose coin signature is pinned to zero at
        compile time.
        """
        coefficients = self._solve(self._condition_bits(condition_values))
        return frozenset(
            position
            for position, row_coefficients, target in self.coin_rows
            if ((row_coefficients & coefficients).bit_count() & 1) ^ target
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of the surface."""
        return {
            "generators": [generator.to_dict() for generator in self.generators],
            "particular": self.particular,
            "kernel": list(self.kernel),
            "constraints": [
                {"position": constraint.position.as_tuple(), "rows": list(constraint.rows)}
                for constraint in self.constraints
            ],
            "coin_rows": [
                [position.as_tuple(), coefficients, target]
                for position, coefficients, target in self.coin_rows
            ],
            "bit_groups": [
                [position.as_tuple() for position in sorted(group)] for group in self.bit_groups
            ],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ConditionalCorrelationSurface:
        """Create a conditional correlation surface from its dictionary representation."""
        return ConditionalCorrelationSurface(
            generators=tuple(
                CorrelationSurface.from_dict(generator) for generator in data["generators"]
            ),
            particular=data["particular"],
            kernel=tuple(data.get("kernel", ())),
            constraints=tuple(
                ConditionalCubeConstraint(
                    Position3D(*constraint["position"]),
                    (tuple(constraint["rows"][0]), tuple(constraint["rows"][1])),
                )
                for constraint in data.get("constraints", ())
            ),
            coin_rows=tuple(
                (Position3D(*position), coefficients, target)
                for position, coefficients, target in data.get("coin_rows", ())
            ),
            bit_groups=tuple(
                frozenset(Position3D(*position) for position in group)
                for group in data.get("bit_groups", ())
            ),
        )


def complete_observable_surfaces(
    graph: BlockGraph,
    observables: Sequence[CorrelationSurface],
    include_nondeterministic: bool = False,
    parallel: bool = True,
) -> list[ConditionalCorrelationSurface]:
    """Complete partial observable surfaces of a block graph with conditional cubes.

    Each partial surface is an exact specification on the edges it spans, as in
    :func:`~tqec.computation.correlation.find_correlation_surface_containing`, and is
    completed into a valid correlation surface satisfying the closure of every static leaf,
    with the closure of the conditional cubes deferred to
    :meth:`ConditionalCorrelationSurface.resolve`. The external identity of the observable is
    pinned at compile time so that every branch resolves to the same observable class: the
    Pauli operators at the ports not already pinned by the partial surface, and the coin
    signature at the initialization leaves, are fixed to the values of a reference
    completion (the all-zero branch assignment when solvable, else any completion of the
    partial surface alone).

    Args:
        graph: The block graph to complete the observables of.
        observables: The partial correlation surfaces specifying the observables.
        include_nondeterministic: Whether the completions may terminate anticommuting on
            initialization leaf cubes, each contributing one uniformly random logical coin to
            the parity, e.g. for the readout bits of the computation. Anticommuting
            terminations on measurement-type leaves are never allowed: the records they would
            require do not exist. Default is ``False``: the completions are deterministic in
            every branch.
        parallel: Whether to use multiprocessing to speed up the search. Default is ``True``.

    Returns:
        One :class:`ConditionalCorrelationSurface` per input partial surface, in order. On a
        graph without conditional cubes the results carry no constraints and
        :meth:`ConditionalCorrelationSurface.resolve` is constant.

    Raises:
        TQECError: If a partial surface is degenerate, spans edges outside the graph or
            assigns Pauli operators inconsistent with the edge types, or cannot be completed
            into a valid correlation surface regardless of the branch assignments.

    """
    relaxed_sources = _source_leaf_paulis(graph) if include_nondeterministic else {}
    positioned = _relaxed_positioned_zx(graph, relaxed_sources)
    conditional_cubes = sorted(graph.conditional_cubes, key=lambda c: c.position)
    return [
        _complete_partial_surface(
            graph,
            positioned,
            partial,
            conditional_cubes,
            relaxed_sources,
            pin_identity=True,
            parallel=parallel,
        )
        for partial in observables
    ]


def complete_condition_surface(
    graph: BlockGraph,
    conditional_cube_position: Position3D,
    parallel: bool = True,
) -> ConditionalCorrelationSurface:
    """Complete the partial condition surface of a conditional cube into evaluable parities.

    The completion lives on the strict past of the conditional cube, so that every physical
    measurement record it collects is available before the branch must be selected. Within
    the past, the completion must match the basis of every measurement-type leaf it
    terminates on, may terminate anticommuting on initialization leaves, contributing one
    uniformly random logical coin to the parity each, e.g. the randomness of a lattice
    surgery merge outcome, and may dangle at the interfaces to the future, tracking the Pauli
    frame of the dangling logical operators.

    If earlier conditional cubes lie in the past, the returned surface carries one closure
    constraint per such cube: the runtime evaluates the conditions in causal order, resolving
    each with the already-known earlier bits. Unlike observables, no external identity is
    pinned: the interfaces and coins of the completion may differ per branch, mirroring how
    Pauli frame updates differ per branch.

    Args:
        graph: The block graph containing the conditional cube.
        conditional_cube_position: The position of the conditional cube whose condition to
            complete.
        parallel: Whether to use multiprocessing to speed up the search. Default is ``True``.

    Returns:
        The completed condition as a :class:`ConditionalCorrelationSurface` whose
        dependencies are (a subset of) the earlier conditional cubes.

    Raises:
        TQECError: If the cube at the given position is not a conditional cube, or the
            partial condition surface is degenerate, spans edges outside the past of the cube,
            assigns Pauli operators inconsistent with the edge types, or cannot be completed
            regardless of the earlier branch assignments.

    """
    cube = graph[conditional_cube_position]
    if not cube.is_conditional or cube.condition is None:
        raise TQECError(
            f"The cube at {conditional_cube_position} is not a conditional cube with a condition."
        )
    z_cut = conditional_cube_position.z
    relaxed_sources = {
        position: pauli
        for position, pauli in _source_leaf_paulis(graph).items()
        if position.z < z_cut
    }
    positioned = _past_slab_positioned_zx(graph, z_cut, relaxed_sources)
    earlier_conditional = sorted(
        (c for c in graph.conditional_cubes if c.position.z < z_cut), key=lambda c: c.position
    )
    return _complete_partial_surface(
        graph,
        positioned,
        cube.condition,
        earlier_conditional,
        relaxed_sources,
        pin_identity=False,
        parallel=parallel,
    )


def _complete_partial_surface(
    graph: BlockGraph,
    positioned: PositionedZX,
    partial: CorrelationSurface,
    conditional_cubes: Sequence[Cube],
    relaxed_sources: Mapping[Position3D, Pauli],
    pin_identity: bool,
    parallel: bool,
) -> ConditionalCorrelationSurface:
    """Complete a partial surface on the given (relaxed) graph into the runtime system."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _cut_edges_as_boundary_pairs,
        _find_correlation_surfaces_with_vertex_ordering,
        _restore_correlation_surface_from_added_vertices,
        _xor_correlation_surfaces,
    )
    from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

    zx_graph = positioned.g
    _check_spiders_are_supported(zx_graph)
    p2v = positioned.p2v

    # Collect and validate the Pauli operators on the half-edges of the partial surface.
    half_edge_paulis: dict[tuple[int, int], Pauli] = {}
    for zx_edge in partial.span:
        (pos_u, basis_u), (pos_v, basis_v) = zx_edge.u, zx_edge.v
        u, v = p2v.get(pos_u), p2v.get(pos_v)
        if zx_edge.is_self_loop:
            raise TQECError(
                f"Edge {(pos_u, pos_v)} of the partial surface is a self-loop, which is not "
                "supported here."
            )
        if u is None or v is None or not zx_graph.connected(u, v):
            raise TQECError(f"Edge {(pos_u, pos_v)} of the partial surface is not in the graph.")
        half_edge_paulis[(u, v)] = half_edge_paulis.get((u, v), Pauli.I) ^ basis_u.to_pauli()
        half_edge_paulis[(v, u)] = half_edge_paulis.get((v, u), Pauli.I) ^ basis_v.to_pauli()
    for (u, v), pauli in half_edge_paulis.items():
        if half_edge_paulis[(v, u)] is not pauli.flipped(is_hadamard(zx_graph, (u, v))):
            raise TQECError(
                f"The Pauli operators of the partial surface on the edge {(u, v)} are "
                "inconsistent with the edge type."
            )

    # Cut the specified edges into dangling boundary pairs so that the search keeps the
    # generators' resolution at them; keep the closed surfaces so that the generators span
    # the full space satisfying the static closures, which the runtime repairs draw from.
    cut_graph, added_vertices = _cut_edges_as_boundary_pairs(zx_graph, half_edge_paulis)
    vertex_ordering = _time_slice_ordering(positioned)
    if vertex_ordering is not None:
        # keep the partition valid by assigning each boundary vertex to its endpoint's part
        vertex_ordering = [
            part | {b for b, (inside, _) in added_vertices.items() if inside in part}
            for part in vertex_ordering
        ]
    internal_generators = _find_correlation_surfaces_with_vertex_ordering(
        cut_graph,
        vertex_ordering,
        parallel,
        keep_closed_surfaces=True,
    )
    if not internal_generators:
        raise TQECError("There is no valid correlation surface on the graph.")
    internal_generators = sorted(internal_generators, key=lambda cs: cs.bits)
    # The multiprocessing search returns surfaces holding per-worker pickled copies of the
    # space, all with identical layouts: re-point them to a single canonical space before
    # extending it, so the extension is visible to every generator.
    space = internal_generators[0].space
    for generator in internal_generators:
        generator.space = space
    # also allocate the positions of the cut edges, which are restored into the generators
    space.register_graph(zx_graph)

    boundary_mask = 0
    spec_target = 0
    for boundary_vertex, edge in added_vertices.items():
        position = space.positions[(boundary_vertex, edge[0])]
        boundary_mask |= 3 << position
        spec_target |= half_edge_paulis[edge].value << position
    if not spec_target:
        raise TQECError(
            "The partial surface is degenerate: its required Pauli operators cancel to "
            "identity on every edge it spans."
        )

    def leaf_bit(position: Position3D) -> int:
        v = p2v[position]
        return space.positions[(v, next(iter(cut_graph.neighbors(v))))]

    # The violation vector of a closure functional: bit i is set exactly when generator i
    # anticommutes with the matched Pauli at the leaf. Violations are linear over XOR, so the
    # value on any combination is the parity of the masked vector.
    def violation_vector(position: Position3D, matched: Pauli) -> int:
        bit_position = leaf_bit(position)
        vector = 0
        for i, generator in enumerate(internal_generators):
            vector |= _violation_bit(generator.bits, bit_position, matched) << i
        return vector

    constraint_vectors = [
        (
            cube.position,
            (
                violation_vector(
                    cube.position,
                    _matched_pauli(cast(ConditionalCubeKind, cube.kind).branches[0]),
                ),
                violation_vector(
                    cube.position,
                    _matched_pauli(cast(ConditionalCubeKind, cube.kind).branches[1]),
                ),
            ),
        )
        for cube in conditional_cubes
    ]
    coin_vectors = [
        (position, violation_vector(position, matched))
        for position, matched in sorted(relaxed_sources.items())
    ]

    # The pinned block: the partial surface spec, plus, for observables, the identity bits
    # (port Paulis and coin signature) fixed to a reference completion so that every branch
    # resolves to the same observable class.
    spec_signatures = [generator.bits & boundary_mask for generator in internal_generators]
    pinned_signatures = list(spec_signatures)
    pinned_target = spec_target
    if pin_identity:
        port_bits = [leaf_bit(graph.ports[label]) for label in graph.ordered_ports]
        reference = _reference_combination(
            spec_signatures, spec_target, [rows[0] for _, rows in constraint_vectors]
        )
        identity_shift = space.num_bits
        identity_target = 0
        for i, generator in enumerate(internal_generators):
            identity_signature = 0
            for shift, bit_position in enumerate(port_bits):
                identity_signature |= ((generator.bits >> bit_position) & 3) << (2 * shift)
            for shift, (_, vector) in enumerate(coin_vectors):
                identity_signature |= ((vector >> i) & 1) << (2 * len(port_bits) + shift)
            pinned_signatures[i] |= identity_signature << identity_shift
            if (reference >> i) & 1:
                identity_target ^= identity_signature
        pinned_target |= identity_target << identity_shift

    # Echelon-reduce the pinned block once, tracking the generator-index masks: the
    # particular combination satisfies the pinned rows, and the kernel masks span the
    # combinations acting trivially on them.
    echelon: dict[int, tuple[int, int]] = {}
    kernel_masks: list[int] = []
    for i, signature in enumerate(pinned_signatures):
        reduced = _reduce_row(echelon, signature, 1 << i, insert=True)
        if reduced is not None and reduced[1]:
            kernel_masks.append(reduced[1])
    particular = _reduce_row(echelon, pinned_target, 0, insert=False)
    if particular is None:
        raise TQECError(
            "The partial surface cannot be completed into a valid correlation surface: its "
            "required Pauli operators (or the pinned identity) are outside the span of the "
            "correlation surfaces satisfying the static leaves."
        )

    # Reduce the kernel to at most one element per distinct closure/coin signature: only
    # those signatures matter to the runtime system and the coin classification.
    def kernel_signature(mask: int) -> int:
        signature = 0
        shift = 0
        for _, rows in constraint_vectors:
            for vector in rows:
                signature |= ((vector & mask).bit_count() & 1) << shift
                shift += 1
        for _, vector in coin_vectors:
            signature |= ((vector & mask).bit_count() & 1) << shift
            shift += 1
        return signature

    kernel_echelon: dict[int, tuple[int, int]] = {}
    reduced_kernel = [
        mask
        for mask in kernel_masks
        if _reduce_row(kernel_echelon, kernel_signature(mask), mask, insert=True) is None
    ]

    def row_over_kernel(vector: int) -> tuple[int, int]:
        coefficients = 0
        for j, mask in enumerate(reduced_kernel):
            coefficients |= ((vector & mask).bit_count() & 1) << j
        target = (vector & particular[1]).bit_count() & 1
        return coefficients, target

    constraints = tuple(
        ConditionalCubeConstraint(position, (row_over_kernel(rows[0]), row_over_kernel(rows[1])))
        for position, rows in constraint_vectors
    )
    coin_rows = tuple((position, *row_over_kernel(vector)) for position, vector in coin_vectors)

    # Group the conditional cubes sharing one classical bit, i.e. equal condition surfaces.
    groups: dict[CorrelationSurface, list[Position3D]] = {}
    for cube in conditional_cubes:
        assert cube.condition is not None
        groups.setdefault(cube.condition, []).append(cube.position)
    bit_groups = tuple(frozenset(positions) for positions in groups.values() if len(positions) > 1)

    # Convert to the public representation in the (particular, kernel) basis: the raw
    # generators are generally inconsistent on the two halves of a cut edge, which the public
    # span cannot represent, whereas the particular combination realizes the partial surface
    # exactly and the kernel combinations act trivially on the cut edges. The stored masks
    # are re-expressed in this basis, keeping the constraint and coin rows unchanged since
    # they already live over the kernel coordinates.
    def to_public(mask: int) -> CorrelationSurface:
        combined = _xor_correlation_surfaces(
            [generator for i, generator in enumerate(internal_generators) if (mask >> i) & 1]
        )
        restored = _restore_correlation_surface_from_added_vertices(combined, added_vertices)
        return restored.to_immutable_public_representation(positioned)

    return ConditionalCorrelationSurface(
        generators=(to_public(particular[1]), *(to_public(mask) for mask in reduced_kernel)),
        particular=0b1,
        kernel=tuple(0b10 << j for j in range(len(reduced_kernel))),
        constraints=constraints,
        coin_rows=coin_rows,
        bit_groups=bit_groups,
    )


def _reduce_row(
    echelon: dict[int, tuple[int, int]], vector: int, mask: int, insert: bool
) -> tuple[int, int] | None:
    """Reduce ``(vector, mask)`` against the echelon rows, XORing the masks along.

    If the vector reduces to zero, return the reduced ``(0, mask)`` pair: ``mask`` is then a
    combination reproducing the original vector from the echelon rows (a kernel element when
    the original row came from a generator, a solution when it was a target). Otherwise the
    row is independent: return ``None`` after inserting it if ``insert`` is set.
    """
    while vector:
        lead = vector.bit_length() - 1
        if lead not in echelon:
            if insert:
                echelon[lead] = (vector, mask)
            return None
        pivot_vector, pivot_mask = echelon[lead]
        vector ^= pivot_vector
        mask ^= pivot_mask
    return (0, mask)


def _reference_combination(
    spec_signatures: Sequence[int], spec_target: int, zero_branch_vectors: Sequence[int]
) -> int:
    """Return a reference completion pinning the observable identity across the branches.

    Prefer a completion satisfying the spec and the closure of the all-zero branch
    assignment; if none exists, fall back to a completion of the spec alone. The identity
    bits of the returned combination are pinned for every branch, so an all-zero-invalid
    reference merely makes some branches unsolvable at runtime, reported by
    :meth:`ConditionalCorrelationSurface.resolve`.
    """
    for with_closure in (True, False):
        echelon: dict[int, tuple[int, int]] = {}
        shift = max((signature.bit_length() for signature in spec_signatures), default=0)
        for i, signature in enumerate(spec_signatures):
            augmented = signature
            if with_closure:
                for j, vector in enumerate(zero_branch_vectors):
                    augmented |= ((vector >> i) & 1) << (shift + j)
            _reduce_row(echelon, augmented, 1 << i, insert=True)
        solution = _reduce_row(echelon, spec_target, 0, insert=False)
        if solution is not None:
            return solution[1]
    raise TQECError(
        "The partial surface cannot be completed into a valid correlation surface: its "
        "required Pauli operators are outside the span of the correlation surfaces "
        "satisfying the static leaves."
    )


def _matched_pauli(kind: StaticCubeKind) -> Pauli:
    """Return the Pauli operator a correlation surface may terminate with on a closed leaf."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.interop.pyzx.utils import cube_kind_to_zx, vertex_type_to_pauli  # noqa: PLC0415

    return vertex_type_to_pauli(*cube_kind_to_zx(kind)).flipped()


def _violation_bit(bits: int, position: int, matched: Pauli) -> int:
    """Whether the Pauli at the half-edge position anticommutes with the matched Pauli."""
    x = (bits >> position) & 1
    z = (bits >> (position + 1)) & 1
    if matched is Pauli.Z:
        return x
    if matched is Pauli.X:
        return z
    return x ^ z  # matched is Pauli.Y


def _source_leaf_paulis(graph: BlockGraph) -> dict[Position3D, Pauli]:
    """Map each initialization leaf cube position to its matched termination Pauli.

    An initialization (source) leaf cube is a non-port, non-conditional leaf cube whose single
    pipe goes up in time: only its bottom, initialization, temporal face is exposed. A
    correlation surface terminating there in an anticommuting basis is still evaluable, since
    an initialization produces no measurement records, and contributes one uniformly random
    logical coin to the parity. Measurement-type leaves (pipe from above) and sideways leaves
    (spatial pipe, exposing a measurement face) admit no such relaxation: the records an
    anticommuting termination would require do not exist.
    """
    sources: dict[Position3D, Pauli] = {}
    for cube in graph.leaf_cubes:
        if cube.is_port or cube.is_conditional:
            continue
        pipe = graph.pipes_at(cube.position)[0]
        other = pipe.v if pipe.u.position == cube.position else pipe.u
        if other.position.z == cube.position.z + 1:
            sources[cube.position] = _matched_pauli(cast(StaticCubeKind, cube.kind))
    return sources


def _relaxed_positioned_zx(
    graph: BlockGraph, relaxed_sources: Mapping[Position3D, Pauli]
) -> PositionedZX:
    """Convert to a positioned ZX graph, opening conditional cubes and relaxed source leaves.

    The conditional cubes and the given initialization leaves are represented as open BOUNDARY
    vertices so that the surface search keeps the generators' resolution at them; their
    closure constraints are applied afterwards, at runtime for the conditional cubes and as
    coin classification for the initialization leaves.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415
    from pyzx.utils import EdgeType, VertexType  # noqa: PLC0415

    from tqec.interop.pyzx.positioned import PositionedZX  # noqa: PLC0415
    from tqec.interop.pyzx.utils import cube_kind_to_zx  # noqa: PLC0415

    g = GraphS()
    v2p: dict[int, Position3D] = {}
    p2v: dict[Position3D, int] = {}
    for cube in sorted(graph.cubes, key=lambda c: c.position):
        if cube.is_conditional or cube.position in relaxed_sources:
            vt, phase = VertexType.BOUNDARY, 0
        else:
            vt, phase = cube_kind_to_zx(cube.kind)
        v = g.add_vertex(vt, phase=phase)
        v2p[v] = cube.position
        p2v[cube.position] = v
    for pipe in graph.pipes:
        et = EdgeType.HADAMARD if pipe.kind.has_hadamard else EdgeType.SIMPLE
        g.add_edge((p2v[pipe.u.position], p2v[pipe.v.position]), et)
    return PositionedZX(g, v2p)


def _past_slab_positioned_zx(
    graph: BlockGraph, z_cut: int, relaxed_sources: Mapping[Position3D, Pauli]
) -> PositionedZX:
    """Build the positioned ZX graph of the strict past of the given time coordinate.

    Cubes at ``z >= z_cut`` are dropped. A pipe crossing the cut is replaced by a dangling
    BOUNDARY stub at the vacated future endpoint position: the records of the past part of a
    surface dangling at such an interface are all available before the cut, and the dangling
    Pauli is the logical operator whose Pauli frame the parity tracks. The conditional cubes
    and initialization leaves of the past are opened as in :func:`_relaxed_positioned_zx`.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415
    from pyzx.utils import EdgeType, VertexType  # noqa: PLC0415

    from tqec.interop.pyzx.positioned import PositionedZX  # noqa: PLC0415
    from tqec.interop.pyzx.utils import cube_kind_to_zx  # noqa: PLC0415

    g = GraphS()
    v2p: dict[int, Position3D] = {}
    p2v: dict[Position3D, int] = {}
    for cube in sorted(graph.cubes, key=lambda c: c.position):
        if cube.position.z >= z_cut:
            continue
        if cube.is_conditional or cube.position in relaxed_sources:
            vt, phase = VertexType.BOUNDARY, 0
        else:
            vt, phase = cube_kind_to_zx(cube.kind)
        v = g.add_vertex(vt, phase=phase)
        v2p[v] = cube.position
        p2v[cube.position] = v
    for pipe in graph.pipes:
        pos_u, pos_v = pipe.u.position, pipe.v.position
        if pos_u.z >= z_cut and pos_v.z >= z_cut:
            continue
        et = EdgeType.HADAMARD if pipe.kind.has_hadamard else EdgeType.SIMPLE
        if pos_u.z >= z_cut or pos_v.z >= z_cut:
            past, future = (pos_u, pos_v) if pos_v.z >= z_cut else (pos_v, pos_u)
            stub = g.add_vertex(VertexType.BOUNDARY, phase=0)
            v2p[stub] = future
            p2v[future] = stub
            g.add_edge((p2v[past], stub), et)
        else:
            g.add_edge((p2v[pos_u], p2v[pos_v]), et)
    return PositionedZX(g, v2p)


def _time_slice_ordering(positioned: PositionedZX) -> list[set[int]] | None:
    """Return the time-slice vertex ordering speeding up the search on leafy graphs."""
    zx_graph = positioned.g
    num_leaves = sum(1 for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1)
    if num_leaves < _PARTITION_ALONG_TIME_MIN_LEAF_CUBES:
        return None
    time_slices: dict[int, set[int]] = {}
    for position, v in positioned.p2v.items():
        time_slices.setdefault(position.z, set()).add(v)
    if len(time_slices) <= 1:
        return None
    return [time_slices[z] for z in sorted(time_slices)]
