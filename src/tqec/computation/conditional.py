"""Correlation surfaces of computations that contain conditional cubes.

A computation with conditional cubes resolves to a different static computation for each
assignment of the runtime condition bits, so its correlation surfaces are branch-dependent.
They are compiled from user-provided *partial* correlation surfaces, exactly like the
``condition`` attribute of a conditional cube: the partial surface pins the Pauli content of
the observable, and the completion into a full correlation surface is deferred.

The compiled artifact, :class:`ConditionalCorrelationSurface`, is scalable to any number of
conditional cubes: it stores an affine coset of correlation surfaces satisfying the closure
of every *static* leaf (a ``particular`` surface plus a ``kernel`` basis), together with a
small preprocessed GF(2) linear system. Once the relevant condition bits are known at runtime,
:meth:`ConditionalCorrelationSurface.resolve` selects the closure row of each conditional cube
by its resolved branch, solves the system by Gaussian elimination over the (already reduced)
kernel coordinates, and XORs the selected kernel surfaces into the particular surface. No step
enumerates branch assignments, so the compile- and runtime costs are polynomial in the graph
size and the number of conditional cubes.

Two completion entry points share the machinery:

- **Observables** (:func:`complete_observable_surfaces`): completed on the whole graph. The
  external identity of the observable, i.e. its Pauli operators at the ports, is pinned at
  compile time so that every branch resolves to the same observable class.
- **Conditions** (:func:`complete_condition_surface`): the partial condition surface of a
  conditional cube completed on the strict past of the cube. The completion may terminate
  at ports, e.g. magic state preparations whose non-stabilizer input sources the randomness
  of a lattice surgery merge outcome, but must close entirely within the past: a condition is
  a parity of records available before the cube fires, so a completion that could only close
  by extending across the cut into the future signals a simplifiable structure and is
  rejected.

Every static (non-port) leaf is closed: a completion must terminate commuting with the leaf
basis, matching the physical records. Nondeterminism therefore enters exclusively through
ports — in particular, a nondeterministic observable terminates at magic state preparations
(e.g. T states) treated as open ports, and its distribution follows from the pinned port
Pauli and the input state. Anticommuting terminations on static leaves are never allowed:
on measurement-type leaves the records they would require do not exist, and on
initialization leaves the uniformly random parity they would produce is instead expressed
by routing the surface to a port.

Solvability is only certified at compile time for the spec (and pinned identity); whether a
valid completion exists under the branch assignment actually realized is discovered by
:meth:`ConditionalCorrelationSurface.resolve`, which raises a descriptive error on an
unsolvable branch. Conditional cubes are keyed by the classical bit they read, and cubes reading
the same bit collapse into a single closure constraint at compile time, so sharing is intrinsic
to the representation rather than tracked separately. The bit's identity is the *completed*
condition -- the actual parity of records -- so grouping reflects the physical bit rather than
the surface syntax: it merges cubes whose partial conditions differ but complete to the same
parity, and separates cubes whose partial conditions are equal but complete to different parities
(a later cube sees a larger past and may route to records an earlier cube cannot). A condition
that does not complete on its own past is a samplable coin with no record parity; such cubes fall
back to grouping on the partial condition and store no join surface. The completed condition is
retained on the constraint as the bit's identity, the handle by which lowering joins the bit to
the ``OBSERVABLE_INCLUDE`` instructions realizing its parity in the physical circuit, so runtime
resolution reads a precompiled record parity rather than recompiling the surface. Structural
equality of completed conditions is a sound but conservative proxy for "same bit": it never
merges distinct parities, but may miss two that coincide only semantically.
:meth:`ConditionalCorrelationSurface.resolve` still validates that a mapping assigns the same
value to every position wired to one bit.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from tqec.computation._gf2 import _reduce_row, _solve_parity_constraints
from tqec.computation.block_graph import (
    _PARTITION_ALONG_TIME_MIN_LEAF_CUBES,
    BlockGraph,
    _time_slice_partition,
)
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import ConditionalCubeKind, Cube, StaticCubeKind
from tqec.utils.enums import Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

if TYPE_CHECKING:
    from tqec.interop.pyzx.positioned import PositionedZX

_SIMPLIFIABLE_HINT = (
    " This usually means every completion would have to terminate anticommuting on a static "
    "leaf, indicating a simplifiable computation: the parity contains purely "
    "stabilizer-sourced randomness (classically samplable), or a magic-state injection "
    "targets a known stabilizer state and reduces to a direct magic-state preparation."
)


@dataclass(frozen=True)
class ConditionalCubeConstraint:
    """The runtime closure constraint of one classical bit on a completed surface.

    A classical bit is read by one or more conditional cubes: cubes whose conditions complete to
    equal surfaces, or (for a samplable coin that does not complete) whose partial conditions are
    equal, share the same runtime bit (see :attr:`condition`). ``rows[b]`` is the set of closure
    rows that must all hold when the shared bit resolves to ``b``, one row per wired cube whose
    closure is non-trivial in branch ``b``. Each row is a pair ``(coefficients, target)``:
    ``coefficients`` is a bit mask over the kernel coordinates of the
    :class:`ConditionalCorrelationSurface` and ``target`` is the required parity. The resolved
    surface ``particular XOR kernel-combination`` satisfies the branch exactly when the
    combination ``c`` obeys ``parity(coefficients & c) == target`` for every row in ``rows[b]``.

    Attributes:
        positions: The positions of the conditional cubes wired to this classical bit. This is
            the handle :meth:`ConditionalCorrelationSurface.resolve` looks the bit's value up by,
            and the sort/diagnostic key; a mapping resolution requires the same value at every
            position in the set.
        rows: The closure rows selected in each branch, ``(rows[0], rows[1])``, each a tuple of
            ``(coefficients, target)`` pairs over the kernel coordinates.
        condition: The completed condition surface identifying the classical bit, i.e. the parity
            of records the bit evaluates. Shared by every wired cube; stored so that lowering can
            join it to the ``OBSERVABLE_INCLUDE`` instructions realizing the parity in the
            physical circuit. ``None`` when the bit is a samplable coin whose condition does not
            complete to a record parity, or on hand-constructed constraints that omit the join.

    """

    positions: frozenset[Position3D]
    rows: tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]
    condition: ConditionalCorrelationSurface | None = None


@dataclass(frozen=True)
class ConditionalCorrelationSurface:
    """Branch-dependent correlation surface as an affine coset plus a GF(2) linear system.

    The surface of a resolved branch assignment is the XOR of :attr:`particular` with a
    combination of :attr:`kernel` elements solving the closure rows selected by the resolved
    condition bits (:attr:`constraints`). Every such surface satisfies the closure of every
    static leaf and pins the user-specified partial surface and, for observables, the external
    identity at the ports. The :attr:`dependencies` are minimized at compile time: a
    conditional cube is dropped when its closure is trivially satisfied in both branches, and
    when a single kernel combination satisfies every branch of every cube the surface is
    branch-invariant, folded into :attr:`particular`, and emitted with an empty runtime
    system.

    Conditional cubes whose conditions complete to equal surfaces read one classical bit and
    collapse into a single constraint (see :class:`ConditionalCubeConstraint`), so no separate
    bookkeeping of shared bits is needed. :meth:`resolve` still validates that a mapping assigns
    the same value to every position wired to one bit.

    Attributes:
        particular: The reference correlation surface: it satisfies the pinned rows (partial
            surface and, for observables, the external identity) but not necessarily any
            branch closure.
        kernel: The correlation surfaces acting trivially on the pinned rows, reduced at
            compile time to at most one element per distinct closure signature. The
            runtime system's coefficients live over these kernel coordinates: coordinate
            ``j`` corresponds to ``kernel[j]``.
        constraints: The closure constraint of each classical bit the completion may touch, one
            per distinct completed condition, sorted by their least wired position.

    """

    particular: CorrelationSurface
    kernel: tuple[CorrelationSurface, ...] = ()
    constraints: tuple[ConditionalCubeConstraint, ...] = ()

    def __post_init__(self) -> None:
        wired: set[Position3D] = set()
        for constraint in self.constraints:
            if not constraint.positions:
                raise TQECError("A closure constraint must reference at least one position.")
            if constraint.positions & wired:
                raise TQECError("Each conditional cube position must belong to a single bit.")
            wired |= constraint.positions
        object.__setattr__(
            self, "constraints", tuple(sorted(self.constraints, key=lambda c: min(c.positions)))
        )

    @property
    def dependencies(self) -> frozenset[Position3D]:
        """The positions of the conditional cubes whose condition bits select the surface."""
        return frozenset(
            position for constraint in self.constraints for position in constraint.positions
        )

    def _condition_bits(
        self, condition_values: Mapping[Position3D, bool | int] | bool | int
    ) -> list[int]:
        """Return the resolved bit of each constraint, validating shared positions agree."""
        if not isinstance(condition_values, Mapping):
            return [int(bool(condition_values))] * len(self.constraints)
        # ``isinstance`` widens the key/value types away; restore them for the index below.
        values = cast("Mapping[Position3D, bool | int]", condition_values)
        bits: list[int] = []
        for constraint in self.constraints:
            resolved = {int(bool(values[position])) for position in constraint.positions}
            if len(resolved) > 1:
                raise TQECError(
                    f"The conditional cubes at {sorted(constraint.positions)} share one "
                    "condition bit but were given different condition values."
                )
            bits.append(next(iter(resolved)))
        return bits

    def _solve(self, bits: Sequence[int]) -> int:
        """Solve the closure rows selected by the bits for a kernel-coefficient mask.

        Raises:
            TQECError: If the selected rows are inconsistent, i.e. the completion does not
                exist under this branch assignment.

        """
        rows = [
            row for constraint, bit in zip(self.constraints, bits) for row in constraint.rows[bit]
        ]
        solution = _solve_parity_constraints(rows, len(self.kernel))
        if solution is None:
            resolution = {
                position: bit
                for constraint, bit in zip(self.constraints, bits)
                for position in constraint.positions
            }
            raise TQECError(
                "The conditional correlation surface has no valid resolution when "
                f"the conditional cubes resolve to {resolution}."
            )
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
        surface = self.particular
        for j, kernel_surface in enumerate(self.kernel):
            if (coefficients >> j) & 1:
                surface = surface ^ kernel_surface
        return surface

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of the surface."""
        return {
            "particular": self.particular.to_dict(),
            "kernel": [kernel_surface.to_dict() for kernel_surface in self.kernel],
            "constraints": [
                {
                    "positions": [position.as_tuple() for position in sorted(constraint.positions)],
                    "rows": [
                        [list(row) for row in constraint.rows[0]],
                        [list(row) for row in constraint.rows[1]],
                    ],
                    "condition": (
                        None if constraint.condition is None else constraint.condition.to_dict()
                    ),
                }
                for constraint in self.constraints
            ],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ConditionalCorrelationSurface:
        """Create a conditional correlation surface from its dictionary representation."""
        return ConditionalCorrelationSurface(
            particular=CorrelationSurface.from_dict(data["particular"]),
            kernel=tuple(
                CorrelationSurface.from_dict(kernel_surface)
                for kernel_surface in data.get("kernel", ())
            ),
            constraints=tuple(
                ConditionalCubeConstraint(
                    positions=frozenset(
                        Position3D(*position) for position in constraint["positions"]
                    ),
                    rows=(
                        tuple((row[0], row[1]) for row in constraint["rows"][0]),
                        tuple((row[0], row[1]) for row in constraint["rows"][1]),
                    ),
                    condition=(
                        None
                        if constraint.get("condition") is None
                        else ConditionalCorrelationSurface.from_dict(constraint["condition"])
                    ),
                )
                for constraint in data.get("constraints", ())
            ),
        )


def complete_observable_surfaces(
    graph: BlockGraph,
    observables: Sequence[CorrelationSurface],
    parallel: bool = True,
) -> list[ConditionalCorrelationSurface]:
    """Complete partial observable surfaces of a block graph with conditional cubes.

    Each partial surface is an exact specification on the edges it spans, as in
    :func:`~tqec.computation.correlation.find_correlation_surface_containing`, and is
    completed into a valid correlation surface satisfying the closure of every static leaf,
    with the closure of the conditional cubes deferred to
    :meth:`ConditionalCorrelationSurface.resolve`. The external identity of the observable is
    pinned at compile time so that every branch resolves to the same observable class: the
    Pauli operators at the ports not already pinned by the partial surface are fixed to the
    values of a reference completion (the all-zero branch assignment when solvable, else any
    completion of the partial surface alone).

    The completions must terminate commuting with every static leaf: nondeterministic
    observables are expressed by terminating at ports, e.g. magic state preparations treated
    as open ports, whose pinned port Pauli together with the input state determines the
    observable's distribution. A parity containing purely stabilizer-sourced randomness
    (an anticommuting termination on an initialization leaf) is not representable.

    Args:
        graph: The block graph to complete the observables of.
        observables: The partial correlation surfaces specifying the observables.
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
    positioned, future_stubs = _open_positioned_zx(graph)
    conditional_cubes = sorted(graph.conditional_cubes, key=lambda c: c.position)
    condition_key = _make_condition_key_resolver(graph, parallel)
    return [
        _complete_partial_surface(
            graph,
            positioned,
            partial,
            conditional_cubes,
            condition_key,
            future_stubs,
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
    the past, the completion must terminate commuting with every static leaf and may terminate
    at ports, e.g. the magic state preparation whose non-stabilizer input sources the
    randomness of a lattice surgery merge outcome. It must close entirely within the past: a
    completion that could only close by extending across the cut into the future is rejected,
    since the condition would then depend on a future logical operator rather than on past
    records, signalling a simplifiable structure in which the condition is not needed.

    If earlier conditional cubes lie in the past, the returned surface carries one closure
    constraint per such cube: the runtime evaluates the conditions in causal order, resolving
    each with the already-known earlier bits. Unlike observables, no external identity is
    pinned: the port terminations of the completion may differ per branch, mirroring how
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
    # Complete this cube's condition directly so an un-completable (simplifiable) condition raises
    # the descriptive error, while its strictly-earlier dependencies are keyed by the tolerant
    # resolver (which falls back to their partial conditions when they are themselves samplable).
    condition_key = _make_condition_key_resolver(graph, parallel)
    return _complete_condition(graph, conditional_cube_position, condition_key, parallel)


def _make_condition_key_resolver(
    graph: BlockGraph, parallel: bool
) -> Callable[[Position3D], ConditionalCorrelationSurface | None]:
    """Return a memoized resolver from a conditional cube position to its completed condition.

    The completed condition is the identity of the classical bit the cube reads: two cubes whose
    conditions complete to equal surfaces share one bit. Completing a condition may recurse into
    the completed conditions of strictly-earlier conditional cubes (its own dependencies), so the
    resolver caches by position to complete each condition at most once and to keep the causal
    recursion well-founded (a condition lives on its cube's strict past, so it can only depend on
    earlier cubes). Only the conditions actually reached are completed.

    A condition that cannot be completed on its own past -- a samplable coin whose parity is
    purely stabilizer-sourced -- is not a record parity and has no completed identity; the
    resolver returns ``None`` for it, and the caller falls back to the partial condition to still
    recognize cubes that share such a coin. ``None`` is cached like any other result.
    """
    cache: dict[Position3D, ConditionalCorrelationSurface | None] = {}

    def resolve(position: Position3D) -> ConditionalCorrelationSurface | None:
        if position not in cache:
            try:
                cache[position] = _complete_condition(graph, position, resolve, parallel)
            except TQECError:
                cache[position] = None
        return cache[position]

    return resolve


def _complete_condition(
    graph: BlockGraph,
    position: Position3D,
    condition_key: Callable[[Position3D], ConditionalCorrelationSurface | None],
    parallel: bool,
) -> ConditionalCorrelationSurface:
    """Complete the condition of one conditional cube, keying earlier bits via ``condition_key``."""
    cube = graph[position]
    if not cube.is_conditional or cube.condition is None:
        raise TQECError(f"The cube at {position} is not a conditional cube with a condition.")
    z_cut = position.z
    positioned, future_stubs = _open_positioned_zx(graph, z_cut)
    earlier_conditional = sorted(
        (c for c in graph.conditional_cubes if c.position.z < z_cut), key=lambda c: c.position
    )
    return _complete_partial_surface(
        graph,
        positioned,
        cube.condition,
        earlier_conditional,
        condition_key,
        future_stubs,
        pin_identity=False,
        parallel=parallel,
    )


def _complete_partial_surface(
    graph: BlockGraph,
    positioned: PositionedZX,
    partial: CorrelationSurface,
    conditional_cubes: Sequence[Cube],
    condition_key: Callable[[Position3D], ConditionalCorrelationSurface | None],
    future_stubs: frozenset[Position3D],
    pin_identity: bool,
    parallel: bool,
) -> ConditionalCorrelationSurface:
    """Complete a partial surface on the given (opened) graph into the runtime system."""
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
    # generators' resolution at them. The conditional cubes and ports are already open
    # boundary leaves, so the generators span every correlation surface satisfying the
    # static closures with the required resolution at the spec: surfaces closed on every open
    # leaf are pure gauge (trivial on the pinned rows and on every closure functional)
    # and drop out of the reduction below, so they need not be kept by the search.
    cut_graph, added_vertices = _cut_edges_as_boundary_pairs(zx_graph, half_edge_paulis)
    vertex_ordering = _time_slice_ordering(positioned)
    if vertex_ordering is not None:
        # keep the partition valid by assigning each boundary vertex to its endpoint's part
        vertex_ordering = [
            part | {b for b, (inside, _) in added_vertices.items() if inside in part}
            for part in vertex_ordering
        ]
    internal_generators = _find_correlation_surfaces_with_vertex_ordering(
        cut_graph, vertex_ordering, parallel
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

    # A condition surface must close entirely within the strict past: it may terminate only on
    # past static leaves (records) and past ports (magic-state sources), never at or beyond the
    # causal cut. ``future_stubs`` are exactly the interfaces at the cut -- parallel worldlines
    # continuing into the future and the conditional cube's own not-yet-fired interface -- and
    # terminating on any of them makes the parity depend on a future (yet-unmeasured) logical
    # operator instead of on past records. Pin each to identity unless the spec itself spans it
    # (a condition may be declared directly on the cube's interface), in which case
    # ``boundary_mask`` above already pins it to the partial surface. If this renders the system
    # unsolvable the completion could only close by escaping across the cut (or anticommuting on
    # a static leaf), signalling a simplifiable structure -- e.g. a magic-state injection onto a
    # known stabilizer state, whose merge outcome is a classically samplable stabilizer coin.
    spec_vertices = {u for u, _ in half_edge_paulis}
    future_identity_mask = 0
    for position in future_stubs:
        if p2v[position] not in spec_vertices:
            future_identity_mask |= 3 << leaf_bit(position)

    # The pinned block: the partial surface spec and the future-stub identity pins, plus, for
    # observables, the identity bits (port Paulis) fixed to a reference completion so that
    # every branch resolves to the same observable class.
    spec_signatures = [generator.bits & boundary_mask for generator in internal_generators]
    pinned_signatures = [
        signature | (generator.bits & future_identity_mask)
        for signature, generator in zip(spec_signatures, internal_generators)
    ]
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
            "correlation surfaces satisfying the static leaves." + _SIMPLIFIABLE_HINT
        )

    # Reduce the kernel to at most one element per distinct closure signature: only those
    # signatures matter to the runtime system.
    def kernel_signature(mask: int) -> int:
        signature = 0
        shift = 0
        for _, rows in constraint_vectors:
            for vector in rows:
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

    # Convert a generator-index combination to the public representation: the raw internal
    # generators are generally inconsistent on the two halves of a cut edge, which the public
    # span cannot represent, whereas the particular combination realizes the partial surface
    # exactly and the kernel combinations act trivially on the cut edges. The constraint
    # rows already live over the kernel coordinates, so they carry over unchanged:
    # coordinate ``j`` corresponds to ``reduced_kernel[j]``.
    def to_public(mask: int) -> CorrelationSurface:
        combined = _xor_correlation_surfaces(
            [generator for i, generator in enumerate(internal_generators) if (mask >> i) & 1]
        )
        restored = _restore_correlation_surface_from_added_vertices(combined, added_vertices)
        return restored.to_immutable_public_representation(positioned)

    # Build the branch closure rows of each conditional cube over the kernel coordinates,
    # dropping the cubes whose closure is trivially satisfied in both branches: their condition
    # bit neither constrains the surface nor renders any branch unsolvable, so they are not
    # genuine dependencies. This removes, in particular, every conditional cube the completion
    # does not touch, whose branch violation vectors both vanish.
    touched: list[tuple[Position3D, tuple[tuple[int, int], tuple[int, int]]]] = []
    for position, rows in constraint_vectors:
        branch_rows = (row_over_kernel(rows[0]), row_over_kernel(rows[1]))
        if branch_rows == ((0, 0), (0, 0)):
            continue
        touched.append((position, branch_rows))

    # If a single kernel combination satisfies the selected closure of every branch of every
    # touched cube, then one fixed surface is valid regardless of the condition bits: fold that
    # combination into the particular surface and drop the runtime system entirely. No branch is
    # ever unsolvable, so neither dependency nor runtime solve remains -- and no condition needs
    # to be completed, so a branch-invariant observable never triggers condition completion.
    common = _solve_parity_constraints(
        [row for _, branch_rows in touched for row in branch_rows], len(reduced_kernel)
    )
    if common is not None:
        particular_mask = particular[1]
        for j, kernel_mask in enumerate(reduced_kernel):
            if (common >> j) & 1:
                particular_mask ^= kernel_mask
        return ConditionalCorrelationSurface(particular=to_public(particular_mask))

    # Group the surviving cubes by the classical bit they read: cubes whose conditions complete
    # to equal surfaces share one bit, so their branch-``b`` rows must all hold together when that
    # bit resolves to ``b``. The bit's identity is the completed condition when it exists; a
    # samplable coin has no completed identity, so its cubes fall back to grouping on the partial
    # condition and store no join surface. Only genuinely depended-upon cubes are keyed here, so a
    # simplifiable condition on an untouched or branch-invariant cube is never completed.
    partials = {cube.position: cube.condition for cube in conditional_cubes}

    class _Bit:
        __slots__ = ("condition", "positions", "rows")

        def __init__(self, condition: ConditionalCorrelationSurface | None) -> None:
            self.positions: set[Position3D] = set()
            self.rows: tuple[list[tuple[int, int]], list[tuple[int, int]]] = ([], [])
            self.condition = condition

    bits: dict[object, _Bit] = {}
    order: list[object] = []
    for position, branch_rows in touched:
        completed = condition_key(position)
        group_key = completed if completed is not None else partials[position]
        bit = bits.get(group_key)
        if bit is None:
            bit = bits[group_key] = _Bit(completed)
            order.append(group_key)
        bit.positions.add(position)
        for branch in (0, 1):
            # A ``(0, 0)`` row imposes ``0 == 0`` and is redundant; keep the branch minimal.
            if branch_rows[branch] != (0, 0):
                bit.rows[branch].append(branch_rows[branch])

    return ConditionalCorrelationSurface(
        particular=to_public(particular[1]),
        kernel=tuple(to_public(mask) for mask in reduced_kernel),
        constraints=tuple(
            ConditionalCubeConstraint(
                positions=frozenset(bits[group_key].positions),
                rows=(tuple(bits[group_key].rows[0]), tuple(bits[group_key].rows[1])),
                condition=bits[group_key].condition,
            )
            for group_key in order
        ),
    )


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
        "satisfying the static leaves." + _SIMPLIFIABLE_HINT
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


def _open_positioned_zx(
    graph: BlockGraph, z_cut: int | None = None
) -> tuple[PositionedZX, frozenset[Position3D]]:
    """Convert to a positioned ZX graph, opening the conditional cubes.

    The conditional cubes are represented as open BOUNDARY vertices so that the surface
    search keeps the generators' resolution at them; their closure constraints are applied
    afterwards, at runtime. Every static leaf keeps its closed spider: a surface must
    terminate commuting with it, so no anticommuting (coin) terminations exist and the
    only sources of nondeterminism are the ports.

    When ``z_cut`` is given, the graph is restricted to the strict past of that time
    coordinate: cubes at ``z >= z_cut`` are dropped, and a pipe crossing the cut is replaced by
    a BOUNDARY stub at the vacated future endpoint position. The positions of these future
    stubs are returned alongside the graph. A condition surface must close entirely within the
    strict past, so the caller pins every such stub to identity (unless the spec spans it),
    forbidding the completion from terminating at or beyond the cut -- whether on a parallel
    worldline continuing into the future or on the conditional cube's own not-yet-fired
    interface.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from pyzx.graph.graph_s import GraphS  # noqa: PLC0415
    from pyzx.utils import EdgeType, VertexType  # noqa: PLC0415

    from tqec.interop.pyzx.positioned import PositionedZX  # noqa: PLC0415
    from tqec.interop.pyzx.utils import cube_kind_to_zx  # noqa: PLC0415

    g = GraphS()
    v2p: dict[int, Position3D] = {}
    p2v: dict[Position3D, int] = {}
    future_stubs: set[Position3D] = set()
    for cube in sorted(graph.cubes, key=lambda c: c.position):
        if z_cut is not None and cube.position.z >= z_cut:
            continue
        if cube.is_conditional:
            vt, phase = VertexType.BOUNDARY, 0
        else:
            vt, phase = cube_kind_to_zx(cube.kind)
        v = g.add_vertex(vt, phase=phase)
        v2p[v] = cube.position
        p2v[cube.position] = v
    for pipe in graph.pipes:
        pos_u, pos_v = pipe.u.position, pipe.v.position
        u_future = z_cut is not None and pos_u.z >= z_cut
        v_future = z_cut is not None and pos_v.z >= z_cut
        if u_future and v_future:
            continue
        et = EdgeType.HADAMARD if pipe.kind.has_hadamard else EdgeType.SIMPLE
        if u_future or v_future:
            past, future = (pos_u, pos_v) if v_future else (pos_v, pos_u)
            stub = g.add_vertex(VertexType.BOUNDARY, phase=0)
            v2p[stub] = future
            p2v[future] = stub
            future_stubs.add(future)
            g.add_edge((p2v[past], stub), et)
        else:
            g.add_edge((p2v[pos_u], p2v[pos_v]), et)
    return PositionedZX(g, v2p), frozenset(future_stubs)


def _time_slice_ordering(positioned: PositionedZX) -> list[set[int]] | None:
    """Return the time-slice vertex ordering speeding up the search on leafy graphs."""
    zx_graph = positioned.g
    num_leaves = sum(1 for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1)
    if num_leaves < _PARTITION_ALONG_TIME_MIN_LEAF_CUBES:
        return None
    return _time_slice_partition(positioned)
