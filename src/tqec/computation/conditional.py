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

Both are read off a *single* correlation surface sweep of the graph's time slices, held by
:class:`_CompletionContext`: the generators glued after the slices below a cut span exactly the
surfaces living on that strict past, so the stage harvested there completes the conditions of the
cubes at the cut and the last stage completes the observables. A graph is therefore searched once
however many observables and conditions are compiled on it, and the region a completion lives on
is a handful of pinned rows over the harvested stage rather than a separately searched subgraph.
The conditions are nonetheless completed lazily, exactly for the cubes a surface genuinely depends
on, so an uncompletable condition nothing depends on is not an error.

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
to the representation rather than tracked separately. A bit *is* its *completed* condition -- the
actual parity of records -- so grouping reflects the physical bit rather than the surface syntax:
it merges cubes whose partial conditions differ but complete to the same parity, and separates
cubes whose partial conditions are equal but complete to different parities (a later cube sees a
larger past and may route to records an earlier cube cannot). The completed condition is retained
on the constraint as the bit's identity, the handle by which lowering joins the bit to the
``OBSERVABLE_INCLUDE`` instructions realizing its parity in the physical circuit, so runtime
resolution reads a precompiled record parity rather than recompiling the surface. Structural
equality of completed conditions is a sound but conservative proxy for "same bit": it never
merges distinct parities, but may miss two that coincide only semantically.
:meth:`ConditionalCorrelationSurface.resolve` still validates that a mapping assigns the same
value to every position wired to one bit.

Every bit a surface depends on therefore has a completed condition. A condition that cannot be
completed on its own past would be a coin whose randomness is purely stabilizer-sourced; rather
than represent it, the completion is rejected, since such a structure is either purely Clifford
or admits a simplification in which the condition is not needed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Any, cast

from tqec.computation._gf2 import _reduce_row, _solve_parity_constraints
from tqec.computation.block_graph import (
    _PARTITION_ALONG_TIME_MIN_LEAF_CUBES,
    BlockGraph,
)
from tqec.computation.correlation import CorrelationSurface
from tqec.computation.cube import ConditionalCubeKind, StaticCubeKind
from tqec.utils.enums import Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D

if TYPE_CHECKING:
    from tqec.computation._correlation import _SweepStage
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

    A classical bit *is* its completed condition: the parity of records the runtime evaluates to
    select a branch. Conditional cubes whose conditions complete to equal surfaces read the same
    bit (see :attr:`condition`). ``rows[b]`` is the set of closure rows that must all hold when
    the shared bit resolves to ``b``, one row per wired cube whose closure is non-trivial in
    branch ``b``. Each row is a pair ``(coefficients, target)``: ``coefficients`` is a bit mask
    over the kernel coordinates of the :class:`ConditionalCorrelationSurface` and ``target`` is
    the required parity. The resolved surface ``particular XOR kernel-combination`` satisfies the
    branch exactly when the combination ``c`` obeys ``parity(coefficients & c) == target`` for
    every row in ``rows[b]``.

    Attributes:
        positions: The positions of the conditional cubes wired to this classical bit. This is
            the handle :meth:`ConditionalCorrelationSurface.resolve` looks the bit's value up by,
            and the sort/diagnostic key; a mapping resolution requires the same value at every
            position in the set.
        rows: The closure rows selected in each branch, ``(rows[0], rows[1])``, each a tuple of
            ``(coefficients, target)`` pairs over the kernel coordinates.
        condition: The completed condition surface identifying the classical bit, i.e. the parity
            of records the bit evaluates. Shared by every wired cube, and the handle by which
            lowering joins the bit to the ``OBSERVABLE_INCLUDE`` instructions realizing the parity
            in the physical circuit. Always present: a condition that does not complete to a
            record parity is rejected at compile time rather than represented here.

    """

    positions: frozenset[Position3D]
    rows: tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]
    condition: ConditionalCorrelationSurface


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
                    "condition": constraint.condition.to_dict(),
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
                    condition=ConditionalCorrelationSurface.from_dict(constraint["condition"]),
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
    return complete_surfaces(graph, observables, parallel=parallel)[0]


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
    return complete_surfaces(graph, conditions=[conditional_cube_position], parallel=parallel)[1][
        conditional_cube_position
    ]


def complete_surfaces(
    graph: BlockGraph,
    observables: Sequence[CorrelationSurface] = (),
    conditions: Sequence[Position3D] = (),
    parallel: bool = True,
) -> tuple[list[ConditionalCorrelationSurface], dict[Position3D, ConditionalCorrelationSurface]]:
    """Complete observables and conditions of a block graph from one correlation surface search.

    :func:`complete_observable_surfaces` and :func:`complete_condition_surface` are the
    single-purpose views of this function; completing everything a caller needs in one call is
    what shares the search between them. The results are identical to completing each surface on
    its own, up to the arbitrary reference completion pinning the port Paulis an observable's
    partial surface leaves free.

    Args:
        graph: The block graph to complete the surfaces of.
        observables: The partial correlation surfaces specifying the observables, completed on
            the whole graph as in :func:`complete_observable_surfaces`.
        conditions: The positions of the conditional cubes whose conditions to complete, each on
            the strict past of its cube as in :func:`complete_condition_surface`. The conditions
            the returned observables depend on are completed regardless, and carried by their
            closure constraints.
        parallel: Whether to use multiprocessing to speed up the search. Default is ``True``.

    Returns:
        The completed observables, in the order given, and the completed conditions of the
        requested positions, keyed by position.

    Raises:
        TQECError: If a cube at a requested position is not a conditional cube with a condition,
            or if a partial surface is invalid or cannot be completed. See
            :func:`complete_observable_surfaces` and :func:`complete_condition_surface`.

    """
    for position in conditions:
        cube = graph[position]
        if not cube.is_conditional or cube.condition is None:
            raise TQECError(f"The cube at {position} is not a conditional cube with a condition.")
    context = _CompletionContext(graph, observables, parallel)
    condition_key = context.condition_resolver()
    completed_observables = [
        context.complete(spec, context.final_stage, pin_identity=True, condition_key=condition_key)
        for spec in context.observable_specs
    ]
    return completed_observables, {position: condition_key(position) for position in conditions}


class _CompletionContext:
    """The single correlation-surface sweep every completion on a block graph is read off.

    A completion is linear algebra over a generating set of the correlation surfaces of the
    region it lives on: the whole graph for an observable, the strict past of a conditional cube
    for its condition. Sweeping the time slices of the graph once produces every one of those
    generating sets at once (see
    :func:`~tqec.computation._correlation._sweep_correlation_surface_generators`): the generators
    glued after the slices below a cut span exactly the surfaces living on that strict past, with
    the cuts to the future left open as dangling boundary vertices. This
    context holds that sweep, so a graph is searched once no matter how many observables and
    conditions are completed on it, and the region of a completion is expressed as pinned rows
    over the harvested stage rather than as a separately searched subgraph.

    Every edge any completion may pin is cut into a dangling boundary pair up front (see
    :attr:`_added_vertices`), since resolution at an edge only survives the sweep's reductions
    when the edge is cut. The specs sharing one cut set is what a completion pays for the sharing:
    it pins its own cut edges to its spec and every *other* cut edge to be consistent across the
    cut, without which the raw generators, which resolve the two halves of a cut independently,
    could combine into something that is not a correlation surface of the uncut graph.

    The conditions are still completed lazily, on demand from :meth:`condition_resolver`, so that
    a condition is completed exactly when a surface genuinely depends on the bit it defines: an
    uncompletable condition on a cube nothing depends on is never an error.
    """

    def __init__(
        self, graph: BlockGraph, observables: Sequence[CorrelationSurface], parallel: bool
    ) -> None:
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.computation._correlation import (  # noqa: PLC0415
            _check_spiders_are_supported,
            _cut_edges_as_boundary_pairs,
            _sweep_correlation_surface_generators,
        )

        self._graph = graph
        self._positioned = _open_positioned_zx(graph)
        zx_graph = self._positioned.g
        _check_spiders_are_supported(zx_graph)
        self._p2v = self._positioned.p2v
        self._conditional_cubes = sorted(graph.conditional_cubes, key=lambda c: c.position)

        # Validate the spec of every completion the caller may ask for, i.e. the observables and
        # the condition of every conditional cube, and cut every edge they span: the conditional
        # cubes and ports are already open boundary leaves, so the generators then span every
        # correlation surface satisfying the static closures with the required resolution at the
        # specs. Surfaces closed on every open leaf are pure gauge -- trivial on the pinned rows
        # and on every closure functional -- and drop out of the reductions below, so they need
        # not be kept by the search.
        self.observable_specs = [self._half_edge_paulis(surface) for surface in observables]
        self._condition_specs = {
            cube.position: self._half_edge_paulis(cube.condition)
            for cube in self._conditional_cubes
            if cube.condition is not None
        }
        self._cut_graph, self._added_vertices = _cut_edges_as_boundary_pairs(
            zx_graph,
            {
                edge
                for spec in chain(self.observable_specs, self._condition_specs.values())
                for edge in spec
            },
        )
        # The two sides of each cut edge, in a fixed orientation, for the consistency rows.
        boundary_of = {edge: b for b, edge in self._added_vertices.items()}
        self._cut_edges = [
            ((inside, outside), boundary_vertex, boundary_of[(outside, inside)])
            for boundary_vertex, (inside, outside) in self._added_vertices.items()
            if inside < outside
        ]

        # One part per time slice, so that the stages of the sweep are exactly the strict pasts
        # the conditions live on. The boundary vertices of the cut edges are assigned to the part
        # of their inside endpoint, which keeps the partition valid.
        parts: dict[int, set[int]] = {}
        for v, position in self._positioned.positions.items():
            parts.setdefault(position.z, set()).add(v)
        for boundary_vertex, (inside, _) in self._added_vertices.items():
            parts[self._positioned[inside].z].add(boundary_vertex)
        ordering = [parts[z] for z in sorted(parts)]
        stage_of_z = {z: index for index, z in enumerate(sorted(parts))}
        self._condition_stages = {
            position: stage_of_z[position.z] for position in self._condition_specs
        }
        # Sweeping is what makes the strict pasts harvestable, and otherwise only pays off on the
        # leafy graphs where the whole-graph search is the slower option, counted as elsewhere on
        # the leaves of the graph itself rather than on the ones the cuts add.
        num_leaves = sum(1 for v in zx_graph.vertices() if zx_graph.vertex_degree(v) == 1)
        if self._condition_specs or (
            len(ordering) > 1 and num_leaves >= _PARTITION_ALONG_TIME_MIN_LEAF_CUBES
        ):
            self._part_of = {v: index for index, part in enumerate(ordering) for v in part}
        else:
            # The whole graph is searched at once and counts as the single part of one stage.
            ordering = None
            self._part_of = dict.fromkeys(self._cut_graph.vertices(), 0)
        self.stages = {
            stage.part_index: stage
            for stage in _sweep_correlation_surface_generators(
                self._cut_graph, ordering, parallel, set(self._condition_stages.values())
            )
        }
        for stage in self.stages.values():
            # a canonical generator order keeps the completions reproducible
            stage.generators.sort(key=lambda cs: cs.bits)
        self.final_stage = self.stages[max(self.stages)]
        self.space = self.final_stage.space
        # also allocate the positions of the cut edges, which are restored into the generators
        self.space.register_graph(zx_graph)

    def _half_edge_paulis(self, partial: CorrelationSurface) -> dict[tuple[int, int], Pauli]:
        """Collect and validate the Pauli operators on the half-edges of a partial surface."""
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

        zx_graph = self._positioned.g
        half_edge_paulis: dict[tuple[int, int], Pauli] = {}
        for zx_edge in partial.span:
            (pos_u, basis_u), (pos_v, basis_v) = zx_edge.u, zx_edge.v
            u, v = self._p2v.get(pos_u), self._p2v.get(pos_v)
            if zx_edge.is_self_loop:
                raise TQECError(
                    f"Edge {(pos_u, pos_v)} of the partial surface is a self-loop, which is not "
                    "supported here."
                )
            if u is None or v is None or not zx_graph.connected(u, v):
                raise TQECError(
                    f"Edge {(pos_u, pos_v)} of the partial surface is not in the graph."
                )
            half_edge_paulis[(u, v)] = half_edge_paulis.get((u, v), Pauli.I) ^ basis_u.to_pauli()
            half_edge_paulis[(v, u)] = half_edge_paulis.get((v, u), Pauli.I) ^ basis_v.to_pauli()
        for (u, v), pauli in half_edge_paulis.items():
            if half_edge_paulis[(v, u)] is not pauli.flipped(is_hadamard(zx_graph, (u, v))):
                raise TQECError(
                    f"The Pauli operators of the partial surface on the edge {(u, v)} are "
                    "inconsistent with the edge type."
                )
        return half_edge_paulis

    def _in_region(self, vertex: int, stage: _SweepStage) -> bool:
        """Whether the vertex lies in the region the given stage's surfaces are supported on."""
        return self._part_of[vertex] < stage.part_index

    def condition_resolver(self) -> Callable[[Position3D], ConditionalCorrelationSurface]:
        """Return a memoized resolver from a conditional cube position to its completed condition.

        The completed condition is the identity of the classical bit the cube reads: two cubes
        whose conditions complete to equal surfaces share one bit. Completing a condition may
        recurse into the completed conditions of strictly-earlier conditional cubes (its own
        dependencies), so the resolver caches by position to complete each condition at most once
        and to keep the causal recursion well-founded (a condition lives on its cube's strict
        past, so it can only depend on earlier cubes). Only the conditions actually reached are
        completed, so a completion is attempted exactly for the cubes a surface genuinely depends
        on.

        A condition that cannot be completed on its own past is not a parity of records but a coin
        whose randomness is purely stabilizer-sourced. That is rejected rather than represented:
        such a structure is either purely Clifford or admits a simplification in which the
        condition is not needed, so the descriptive completion error propagates to the caller.
        """
        cache: dict[Position3D, ConditionalCorrelationSurface] = {}

        def resolve(position: Position3D) -> ConditionalCorrelationSurface:
            cached = cache.get(position)
            if cached is None:
                spec = self._condition_specs.get(position)
                if spec is None:
                    raise TQECError(
                        f"The cube at {position} is not a conditional cube with a condition."
                    )
                cached = self.complete(
                    spec,
                    self.stages[self._condition_stages[position]],
                    pin_identity=False,
                    condition_key=resolve,
                )
                cache[position] = cached
            return cached

        return resolve

    def complete(
        self,
        spec: Mapping[tuple[int, int], Pauli],
        stage: _SweepStage,
        pin_identity: bool,
        condition_key: Callable[[Position3D], ConditionalCorrelationSurface],
    ) -> ConditionalCorrelationSurface:
        """Complete a partial surface on the region of a sweep stage into the runtime system.

        The stage fixes the region: its generators span the correlation surfaces of the time
        slices it has glued, which is the whole graph for an observable and the strict past of a
        conditional cube for its condition. ``spec`` is the half-edge Pauli map of the partial
        surface, as returned by :meth:`_half_edge_paulis`, and ``pin_identity`` pins the port
        Paulis of a reference completion so that every branch of an observable resolves to the
        same observable class.
        """
        # Needs to be imported here to avoid pulling pyzx when importing this module.
        from tqec.computation._correlation import (  # noqa: PLC0415
            _CorrelationSurface,
            _restore_correlation_surface_from_added_vertices,
        )
        from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

        space = self.space
        generators = stage.generators
        if not generators:
            raise TQECError("There is no valid correlation surface on the graph.")

        # Pin the spec at the boundary vertices of its own cut edges. Every edge it spans lies
        # inside the region: a condition is declared strictly before its conditional cube (see
        # :class:`~tqec.computation.cube.Cube`), so it can neither reach nor cross the causal cut,
        # and an observable is completed on the whole graph. The check guards the pins, which no
        # generator of the region would support.
        boundary_mask = spec_target = 0
        for boundary_vertex, edge in self._added_vertices.items():
            pauli = spec.get(edge)
            if pauli is None:
                continue
            inside, outside = edge
            if not self._in_region(inside, stage):
                raise TQECError(
                    f"Edge {(self._positioned[inside], self._positioned[outside])} of the partial "
                    "surface lies outside the region the completion is confined to."
                )
            position = space.positions[(boundary_vertex, inside)]
            boundary_mask |= 3 << position
            spec_target |= pauli.value << position
        if not spec_target:
            raise TQECError(
                "The partial surface is degenerate: its required Pauli operators cancel to "
                "identity on every edge it spans."
            )

        # A completion must stay within its region: the cuts to the unprocessed time slices are
        # pinned to identity. For a condition this is the rule that it close entirely within the
        # strict past -- it may terminate only on past static leaves (records) and past ports
        # (magic-state sources), never at or beyond the causal cut, where the parity would depend
        # on a future, yet-unmeasured logical operator instead of on past records. The frontier
        # holds exactly the interfaces at the cut: parallel worldlines continuing into the future
        # and the conditional cube's own not-yet-fired interface. It is empty for the last stage,
        # whose region is the whole graph.
        for boundary_vertex, (inside, _) in stage.frontier.items():
            boundary_mask |= 3 << space.positions[(boundary_vertex, inside)]

        pinned_signatures = [generator.bits & boundary_mask for generator in generators]
        pinned_target = spec_target
        shift = space.num_bits

        # Every cut edge this completion does not pin must still be consistent across the cut,
        # since the generators resolve its two half-edges independently and only a consistent
        # combination is a correlation surface of the uncut graph. A cut edge leaving the region
        # is thereby pinned to identity, like the frontier above.
        for edge, boundary_u, boundary_v in self._cut_edges:
            if edge in spec:
                continue
            position_u = space.positions[(boundary_u, edge[0])]
            position_v = space.positions[(boundary_v, edge[1])]
            hadamard = is_hadamard(self._positioned.g, edge)
            for i, generator in enumerate(generators):
                mismatch = ((generator.bits >> position_u) & 3) ^ (
                    Pauli((generator.bits >> position_v) & 3).flipped(hadamard).value
                )
                pinned_signatures[i] |= mismatch << shift
            shift += 2

        def leaf_bit(position: Position3D) -> int:
            v = self._p2v[position]
            return space.positions[(v, next(iter(self._cut_graph.neighbors(v))))]

        # The violation vector of a closure functional: bit i is set exactly when generator i
        # anticommutes with the matched Pauli at the leaf. Violations are linear over XOR, so the
        # value on any combination is the parity of the masked vector. A conditional cube outside
        # the region is supported by no generator, so both its vectors vanish and it drops out
        # below: only the cubes the region contains can constrain the completion.
        def violation_vector(position: Position3D, matched: Pauli) -> int:
            bit_position = leaf_bit(position)
            vector = 0
            for i, generator in enumerate(generators):
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
            for cube in self._conditional_cubes
        ]

        # For observables, append the identity bits (port Paulis) fixed to a reference completion
        # of the pinned rows so that every branch resolves to the same observable class.
        if pin_identity:
            port_bits = [leaf_bit(self._graph.ports[label]) for label in self._graph.ordered_ports]
            reference = _reference_combination(
                pinned_signatures, pinned_target, [rows[0] for _, rows in constraint_vectors]
            )
            identity_target = 0
            for i, generator in enumerate(generators):
                identity_signature = 0
                for offset, bit_position in enumerate(port_bits):
                    identity_signature |= ((generator.bits >> bit_position) & 3) << (2 * offset)
                pinned_signatures[i] |= identity_signature << shift
                if (reference >> i) & 1:
                    identity_target ^= identity_signature
            pinned_target |= identity_target << shift

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
            offset = 0
            for _, rows in constraint_vectors:
                for vector in rows:
                    signature |= ((vector & mask).bit_count() & 1) << offset
                    offset += 1
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

        # Convert a generator-index combination to the public representation: the raw generators
        # are generally inconsistent on the two halves of a cut edge, which the public span cannot
        # represent, whereas the pinned rows make every combination realizing them consistent
        # there. The constraint rows already live over the kernel coordinates, so they carry over
        # unchanged: coordinate ``j`` corresponds to ``reduced_kernel[j]``.
        def to_public(mask: int) -> CorrelationSurface:
            bits = 0
            for i, generator in enumerate(generators):
                if (mask >> i) & 1:
                    bits ^= generator.bits
            restored = _restore_correlation_surface_from_added_vertices(
                _CorrelationSurface(space, bits), self._added_vertices
            )
            return restored.to_immutable_public_representation(self._positioned)

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

        # Group the surviving cubes by the classical bit they read, i.e. by their completed
        # condition: cubes whose conditions complete to equal surfaces share one bit, so their
        # branch-``b`` rows must all hold together when that bit resolves to ``b``. Only genuinely
        # depended-upon cubes are keyed here, so completion is attempted exactly where a bit really
        # selects the surface; a condition that does not complete to a record parity raises rather
        # than being represented.
        class _Bit:
            __slots__ = ("positions", "rows")

            def __init__(self) -> None:
                self.positions: set[Position3D] = set()
                self.rows: tuple[list[tuple[int, int]], list[tuple[int, int]]] = ([], [])

        bits: dict[ConditionalCorrelationSurface, _Bit] = {}
        order: list[ConditionalCorrelationSurface] = []
        for position, branch_rows in touched:
            key = condition_key(position)
            bit = bits.get(key)
            if bit is None:
                bit = bits[key] = _Bit()
                order.append(key)
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
                    positions=frozenset(bits[key].positions),
                    rows=(tuple(bits[key].rows[0]), tuple(bits[key].rows[1])),
                    condition=key,
                )
                for key in order
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


def _open_positioned_zx(graph: BlockGraph) -> PositionedZX:
    """Convert to a positioned ZX graph, opening the conditional cubes.

    The conditional cubes are represented as open BOUNDARY vertices so that the surface
    search keeps the generators' resolution at them; their closure constraints are applied
    afterwards, at runtime. Every static leaf keeps its closed spider: a surface must
    terminate commuting with it, so no anticommuting (coin) terminations exist and the
    only sources of nondeterminism are the ports.
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
        if cube.is_conditional:
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
