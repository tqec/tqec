"""Correlation surfaces of computations that contain conditional cubes.

A computation with conditional cubes resolves to a different static computation for each
assignment of the runtime condition bits, so its correlation surfaces are *families*: one
surface per assignment, represented compactly by a base surface and XOR delta terms over
subsets of the conditional cube positions (:class:`ConditionalCorrelationSurface`).

Two kinds of families are compiled here:

- **Observables** (:func:`find_conditional_correlation_surfaces`): families whose resolution is
  a valid correlation surface of the resolved computation for *every* assignment, sharing the
  same identity, i.e. the same external stabilizer at the ports, the same record-collection
  pattern at the conditional cubes, and, when non-deterministic observables are requested, the
  same coin signature at the initialization leaves. Observable classes that only exist for some
  assignments are excluded: their parity cannot be evaluated on every shot.
- **Conditions** (:func:`complete_condition_surface`): the partial condition surface of a
  conditional cube completed into evaluable parities on the strict past of the cube. The
  completion may terminate anticommuting on initialization leaves, contributing uniformly
  random logical *coins* to the parity, e.g. lattice surgery merge outcomes, and may dangle at
  the interfaces to the future, tracking the Pauli frame of the dangling logical operators.
  Anticommuting terminations on measurement-type leaves are never allowed: the records they
  would require do not exist.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Any, cast

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
    from tqec.computation._correlation import _CorrelationSurface, _CorrelationSurfaceSpace
    from tqec.interop.pyzx.positioned import PositionedZX

_MAX_CONDITIONAL_CUBES = 10
"""Maximum number of conditional cubes resolved jointly: the branch assignments are enumerated
exhaustively, so the cost grows as ``2**k``."""


@dataclass(frozen=True)
class ConditionalCorrelationSurface:
    """Branch-dependent family of correlation surfaces over a conditional computation.

    The family assigns one correlation surface to each assignment of the condition bits of the
    conditional cubes it depends on. It is stored in algebraic normal form: the surface at a
    given assignment is the XOR of :attr:`base` with the delta of every subset of conditional
    cube positions whose condition bits are all 1. A family with no deltas is a static surface
    valid under every assignment.

    Note:
        The delta terms are formal XOR terms: a delta on its own is generally not a valid
        correlation surface. Only the resolved surfaces returned by :meth:`resolve` are.

    Attributes:
        base: The correlation surface at the all-zero assignment.
        deltas: The ANF delta terms as ``(subset of conditional cube positions, delta)`` pairs,
            stored in a canonical order.
        coins: The positions of the initialization leaf cubes contributing a uniformly random
            logical coin to the parity of the all-zero-assignment resolution. Empty for
            deterministic observables. For observable families the coin signature is
            assignment-invariant; for completed conditions it refers to the all-zero
            resolution.

    """

    base: CorrelationSurface
    deltas: tuple[tuple[frozenset[Position3D], CorrelationSurface], ...] = ()
    coins: frozenset[Position3D] = frozenset()

    def __post_init__(self) -> None:
        deltas = tuple((frozenset(positions), delta) for positions, delta in self.deltas)
        seen: set[frozenset[Position3D]] = set()
        for positions, delta in deltas:
            if not positions:
                raise TQECError(
                    "A delta term of a conditional correlation surface must be keyed by a "
                    "non-empty set of conditional cube positions."
                )
            if positions in seen:
                raise TQECError(f"Duplicate delta term for the positions {sorted(positions)}.")
            if not delta.span:
                raise TQECError(
                    "A delta term of a conditional correlation surface must span at least one edge."
                )
            seen.add(positions)
        object.__setattr__(
            self,
            "deltas",
            tuple(
                sorted(
                    deltas,
                    key=lambda term: (len(term[0]), sorted(p.as_tuple() for p in term[0])),
                )
            ),
        )
        object.__setattr__(self, "coins", frozenset(self.coins))

    @property
    def dependencies(self) -> frozenset[Position3D]:
        """The positions of the conditional cubes the family depends on."""
        return frozenset(chain.from_iterable(positions for positions, _ in self.deltas))

    def resolve(
        self, condition_values: Mapping[Position3D, bool | int] | bool | int
    ) -> CorrelationSurface:
        """Return the correlation surface selected by the given condition values.

        Args:
            condition_values: the runtime value(s) of the conditions. If a single boolean (or
                integer) is provided, the condition bits of all the conditional cubes take
                that value. Otherwise, a mapping from the positions of the conditional cubes
                to their respective condition values must be provided, covering at least
                :attr:`dependencies`.

        Returns:
            The correlation surface of the selected branch: :attr:`base` XORed with the delta
            of every subset of conditional cube positions whose condition bits are all 1.

        Raises:
            KeyError: if ``condition_values`` is a mapping and does not contain an entry for
                some position in :attr:`dependencies`.

        """
        surface = self.base
        if isinstance(condition_values, Mapping):
            for positions, delta in self.deltas:
                if all(condition_values[p] for p in positions):
                    surface = surface ^ delta
            return surface
        if bool(condition_values):
            for _, delta in self.deltas:
                surface = surface ^ delta
        return surface

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of the family."""
        return {
            "base": self.base.to_dict(),
            "deltas": [
                {
                    "positions": [p.as_tuple() for p in sorted(positions)],
                    "surface": delta.to_dict(),
                }
                for positions, delta in self.deltas
            ],
            "coins": [p.as_tuple() for p in sorted(self.coins)],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ConditionalCorrelationSurface:
        """Create a conditional correlation surface from its dictionary representation."""
        return ConditionalCorrelationSurface(
            base=CorrelationSurface.from_dict(data["base"]),
            deltas=tuple(
                (
                    frozenset(Position3D(*p) for p in term["positions"]),
                    CorrelationSurface.from_dict(term["surface"]),
                )
                for term in data.get("deltas", ())
            ),
            coins=frozenset(Position3D(*p) for p in data.get("coins", ())),
        )


def find_conditional_correlation_surfaces(
    graph: BlockGraph,
    include_nondeterministic: bool = False,
    parallel: bool = True,
) -> list[ConditionalCorrelationSurface]:
    """Find the correlation surface families of a block graph with conditional cubes.

    The conditional cubes are represented as open leaves during the search, keeping the
    generators' resolution at them, and the closure against the resolved branch bases is
    applied afterwards, once per assignment of the condition bits, by Gaussian elimination
    over GF(2). A returned family has a valid resolution for *every* assignment, all sharing
    the same identity: the same external stabilizer at the ports, the same record-collection
    pattern at the conditional cubes and, if ``include_nondeterministic``, the same coin
    signature at the initialization leaves. Observable classes existing only for some
    assignments are excluded, mirroring how the static search only returns deterministic
    observables: their parity cannot be evaluated on the shots taking the other branches.

    On a graph without conditional cubes and with ``include_nondeterministic`` unset, this
    matches :py:meth:`~tqec.computation.block_graph.BlockGraph.find_correlation_surfaces`,
    with every returned surface wrapped as a delta-free family.

    Args:
        graph: The block graph to find the correlation surface families of.
        include_nondeterministic: Whether to also return non-deterministic families, whose
            parity includes uniformly random logical coins from correlation surfaces
            terminating anticommuting on initialization leaf cubes, e.g. the readout bits of
            the computation. Anticommuting terminations on measurement-type leaves are never
            allowed: the records they would require do not exist. Default is ``False``:
            every returned family is deterministic in every branch.
        parallel: Whether to use multiprocessing to speed up the search. Default is ``True``.

    Returns:
        The list of correlation surface families, in a canonical order.

    Raises:
        TQECError: If the graph contains more than ``2**10`` branch assignments, has no leaf
            node, or if no family valid under every assignment exists.

    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _find_correlation_surfaces_with_vertex_ordering,
        _solve_linear_system,
    )

    conditional_cubes = sorted(graph.conditional_cubes, key=lambda c: c.position)
    if not conditional_cubes and (not include_nondeterministic or len(graph.cubes) == 1):
        # No relaxation requested (or possible, on a single-node graph): delegate to the
        # static search and wrap.
        return [
            ConditionalCorrelationSurface(surface)
            for surface in graph.find_correlation_surfaces(parallel=parallel)
        ]
    if len(conditional_cubes) > _MAX_CONDITIONAL_CUBES:
        raise TQECError(
            f"The graph contains {len(conditional_cubes)} conditional cubes, but resolving "
            f"more than {_MAX_CONDITIONAL_CUBES} jointly is not supported: the branch "
            "assignments are enumerated exhaustively."
        )

    relaxed_sources = _source_leaf_paulis(graph) if include_nondeterministic else {}
    positioned = _relaxed_positioned_zx(graph, relaxed_sources)
    zx_graph = positioned.g
    _check_spiders_are_supported(zx_graph)
    if not any(len(zx_graph.neighbors(v)) == 1 for v in zx_graph.vertices()):
        raise TQECError(
            "The graph must contain at least one leaf node to find correlation surfaces."
        )
    generators = _find_correlation_surfaces_with_vertex_ordering(
        zx_graph,
        _time_slice_ordering(graph, positioned),
        parallel,
        keep_closed_surfaces=True,
    )
    if not generators:
        raise TQECError(_NO_FAMILY_ERROR)
    generators = sorted(generators, key=lambda cs: cs.bits)
    space = generators[0].space

    def leaf_bit(position: Position3D) -> int:
        v = positioned.p2v[position]
        return space.positions[(v, next(iter(zx_graph.neighbors(v))))]

    k = len(conditional_cubes)
    conditional_positions = [cube.position for cube in conditional_cubes]
    conditional_bits = [leaf_bit(position) for position in conditional_positions]
    branch_paulis = [
        (
            _matched_pauli(cast(ConditionalCubeKind, cube.kind).branches[0]),
            _matched_pauli(cast(ConditionalCubeKind, cube.kind).branches[1]),
        )
        for cube in conditional_cubes
    ]
    source_terms = [
        (leaf_bit(position), matched, position)
        for position, matched in sorted(relaxed_sources.items())
    ]
    port_bits = [leaf_bit(graph.ports[label]) for label in graph.ordered_ports]

    # The identity (anchor) of a family: the Pauli operators at the ports, the
    # record-collection bits at the conditional cubes and the coin bits at the relaxed
    # initialization leaves, at fixed shifts so that the anchors of different assignments are
    # directly comparable.
    num_port_bits = 2 * len(port_bits)
    coin_shift = num_port_bits + k
    anchor_width = coin_shift + len(source_terms)

    def make_anchor(assignment: int) -> Callable[[_CorrelationSurface], int]:
        allowed = [branch_paulis[i][(assignment >> i) & 1] for i in range(k)]

        def compute(cs: _CorrelationSurface) -> int:
            bits = cs.bits
            a = 0
            for shift, pos in enumerate(port_bits):
                a |= ((bits >> pos) & 3) << (2 * shift)
            for i in range(k):
                a |= _presence_bit(bits, conditional_bits[i], allowed[i]) << (num_port_bits + i)
            for j, (pos, matched, _) in enumerate(source_terms):
                a |= _violation_bit(bits, pos, matched) << (coin_shift + j)
            return a

        return compute

    def make_constraints(assignment: int) -> Callable[[_CorrelationSurface], int]:
        allowed = [branch_paulis[i][(assignment >> i) & 1] for i in range(k)]

        def compute(cs: _CorrelationSurface) -> int:
            bits = cs.bits
            sig = 0
            for i in range(k):
                sig |= _violation_bit(bits, conditional_bits[i], allowed[i]) << i
            return sig

        return compute

    # The valid surfaces of each assignment: the kernel of the closure constraints at the
    # resolved conditional leaves, and the achievable anchors within it.
    kernels: list[list[_CorrelationSurface]] = []
    anchors: list[Callable[[_CorrelationSurface], int]] = []
    anchor_images: list[list[int]] = []
    for assignment in range(1 << k):
        kernel = _span_kernel(generators, make_constraints(assignment))
        anchor = make_anchor(assignment)
        image_basis: dict[int, tuple[int, int]] = {}
        for cs in kernel:
            _solve_linear_system(image_basis, anchor(cs))
        kernels.append(kernel)
        anchors.append(anchor)
        anchor_images.append([vector for vector, _ in image_basis.values()])

    # The branch-invariant surfaces: valid under every assignment, i.e. acting trivially on
    # every conditional leaf. They are both the delta-free families and the representative
    # freedom of every family, so the anchor-based families are enumerated modulo them.
    def all_strands(cs: _CorrelationSurface) -> int:
        bits = cs.bits
        sig = 0
        for i, pos in enumerate(conditional_bits):
            sig |= ((bits >> pos) & 3) << (2 * i)
        return sig

    branch_invariant = _span_kernel(generators, all_strands)
    anchor_0 = anchors[0]

    # Mirror the static search contract for the branch-invariant families: on a graph with
    # identity bits (ports, or coins when requested), a surface whose identity depends on the
    # other surfaces' identities is a closed deterministic detector and is dropped; on a fully
    # closed graph, every branch-invariant surface is an observable and is kept. The
    # record-collection bits are not identity bits here: they are zero on every
    # branch-invariant surface.
    identity_mask = ((1 << num_port_bits) - 1) | (((1 << len(source_terms)) - 1) << coin_shift)
    if identity_mask:
        identity_basis: dict[int, tuple[int, int]] = {}
        invariant_families = [
            cs
            for cs in branch_invariant
            if _solve_linear_system(identity_basis, anchor_0(cs) & identity_mask) is None
        ]
    else:
        invariant_families = branch_invariant

    # The anchors achievable under every assignment, modulo the branch-invariant anchors.
    common_anchors: list[int] = anchor_images[0] if anchor_width else []
    for image in anchor_images[1:]:
        common_anchors = _intersect_spans(common_anchors, image, anchor_width)
    quotient_basis: dict[int, tuple[int, int]] = {}
    for cs in branch_invariant:
        _solve_linear_system(quotient_basis, anchor_0(cs))
    family_anchors = [
        anchor for anchor in common_anchors if _solve_linear_system(quotient_basis, anchor) is None
    ]

    families = [
        _family_from_assignments([cs.bits], [], space, positioned, source_terms)
        for cs in invariant_families
    ]
    for target in family_anchors:
        per_assignment_bits: list[int] = []
        for assignment in range(1 << k):
            solution = _solve_in_span(kernels[assignment], anchors[assignment], target, space)
            if solution is None:  # pragma: no cover - the target is in every anchor image
                break
            per_assignment_bits.append(solution.bits)
        else:
            families.append(
                _family_from_assignments(
                    per_assignment_bits, conditional_positions, space, positioned, source_terms
                )
            )

    if not families:
        raise TQECError(_NO_FAMILY_ERROR)
    return sorted(families, key=_family_sort_key)


_NO_FAMILY_ERROR = (
    "There is no observable in the block graph that is valid under every resolution of the "
    "conditional cubes. Observable classes existing only for some branch assignments cannot "
    "be evaluated on every shot and are excluded."
)


def complete_condition_surface(
    graph: BlockGraph,
    conditional_cube_position: Position3D,
    parallel: bool = True,
) -> ConditionalCorrelationSurface:
    """Complete the partial condition surface of a conditional cube into evaluable parities.

    The completion lives on the strict past of the conditional cube, so that every physical
    measurement record it collects is available before the branch must be selected. Within the
    past, the completion must match the basis of every measurement-type leaf it terminates on,
    may terminate anticommuting on initialization leaves, contributing one uniformly random
    logical coin to the parity each, e.g. the randomness of a lattice surgery merge outcome,
    and may dangle at the interfaces to the future, tracking the Pauli frame of the dangling
    logical operators.

    If earlier conditional cubes lie in the past, the completion is resolved once per
    assignment of their condition bits, and the resulting family carries delta terms over
    them: the runtime evaluates the conditions in causal order, XORing in the deltas selected
    by the already-resolved bits.

    Args:
        graph: The block graph containing the conditional cube.
        conditional_cube_position: The position of the conditional cube whose condition to
            complete.
        parallel: Whether to use multiprocessing to speed up the search. Default is ``True``.

    Returns:
        The completed condition as a
        :py:class:`~tqec.computation.conditional.ConditionalCorrelationSurface` whose
        dependencies are (a subset of) the earlier conditional cubes.

    Raises:
        TQECError: If the cube at the given position is not a conditional cube, the partial
            condition surface is degenerate, spans edges outside the past of the cube or
            assigns Pauli operators inconsistent with the edge types, or if the condition
            cannot be completed into an evaluable parity under some resolution of the earlier
            conditional cubes.

    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _check_spiders_are_supported,
        _cut_edges_as_boundary_pairs,
        _find_correlation_surfaces_with_vertex_ordering,
        _restore_correlation_surface_from_added_vertices,
    )
    from tqec.interop.pyzx.utils import is_hadamard  # noqa: PLC0415

    cube = graph[conditional_cube_position]
    if not cube.is_conditional or cube.condition is None:
        raise TQECError(
            f"The cube at {conditional_cube_position} is not a conditional cube with a condition."
        )
    z_cut = conditional_cube_position.z
    earlier_conditional = sorted(
        (c for c in graph.conditional_cubes if c.position.z < z_cut), key=lambda c: c.position
    )
    if len(earlier_conditional) > _MAX_CONDITIONAL_CUBES:
        raise TQECError(
            f"The past of the conditional cube contains {len(earlier_conditional)} conditional "
            f"cubes, but resolving more than {_MAX_CONDITIONAL_CUBES} jointly is not supported."
        )

    positioned = _past_slab_positioned_zx(graph, z_cut, _source_leaf_paulis(graph))
    zx_graph = positioned.g
    _check_spiders_are_supported(zx_graph)
    p2v = positioned.p2v

    # Collect and validate the Pauli operators on the half-edges of the partial condition.
    half_edge_paulis: dict[tuple[int, int], Pauli] = {}
    for zx_edge in cube.condition.span:
        (pos_u, basis_u), (pos_v, basis_v) = zx_edge.u, zx_edge.v
        u, v = p2v.get(pos_u), p2v.get(pos_v)
        if zx_edge.is_self_loop:
            raise TQECError(
                f"Edge {(pos_u, pos_v)} of the condition is a self-loop, which is not "
                "supported in a condition surface."
            )
        if u is None or v is None or not zx_graph.connected(u, v):
            raise TQECError(
                f"Edge {(pos_u, pos_v)} of the condition is not in the past of the "
                "conditional cube."
            )
        half_edge_paulis[(u, v)] = half_edge_paulis.get((u, v), Pauli.I) ^ basis_u.to_pauli()
        half_edge_paulis[(v, u)] = half_edge_paulis.get((v, u), Pauli.I) ^ basis_v.to_pauli()
    for (u, v), pauli in half_edge_paulis.items():
        if half_edge_paulis[(v, u)] is not pauli.flipped(is_hadamard(zx_graph, (u, v))):
            raise TQECError(
                f"The Pauli operators of the condition on the edge {(u, v)} are inconsistent "
                "with the edge type."
            )

    # Cut the specified edges into dangling boundary pairs so that the search keeps the
    # generators' resolution at them, including surfaces acting trivially on all the leaves.
    cut_graph, added_vertices = _cut_edges_as_boundary_pairs(zx_graph, half_edge_paulis)
    generators = _find_correlation_surfaces_with_vertex_ordering(cut_graph, None, parallel)
    if not generators:
        raise TQECError(
            "There is no valid correlation surface on the past of the conditional cube."
        )
    generators = sorted(generators, key=lambda cs: cs.bits)
    # also allocate the positions of the cut edges, which are restored in the solutions
    space = generators[0].space.register_graph(zx_graph)

    boundary_mask = 0
    spec_target = 0
    for boundary_vertex, edge in added_vertices.items():
        position = space.positions[(boundary_vertex, edge[0])]
        boundary_mask |= 3 << position
        spec_target |= half_edge_paulis[edge].value << position
    if not spec_target:
        raise TQECError(
            "The condition is degenerate: its required Pauli operators cancel to identity on "
            "every edge it spans."
        )

    def leaf_bit(position: Position3D) -> int:
        v = p2v[position]
        return space.positions[(v, next(iter(cut_graph.neighbors(v))))]

    k = len(earlier_conditional)
    conditional_positions = [c.position for c in earlier_conditional]
    conditional_bits = [leaf_bit(position) for position in conditional_positions]
    branch_paulis = [
        (
            _matched_pauli(cast(ConditionalCubeKind, c.kind).branches[0]),
            _matched_pauli(cast(ConditionalCubeKind, c.kind).branches[1]),
        )
        for c in earlier_conditional
    ]

    # The coin bits are classified on the restored solutions, whose Pauli operators live on
    # the original (uncut) edges, so the source half-edge slots are looked up in the original
    # slab graph rather than in the cut graph.
    def original_leaf_bit(position: Position3D) -> int:
        v = p2v[position]
        return space.positions[(v, next(iter(zx_graph.neighbors(v))))]

    source_terms = [
        (original_leaf_bit(position), matched, position)
        for position, matched in sorted(_source_leaf_paulis(graph).items())
        if position.z < z_cut
    ]
    constraint_shift = space.num_bits

    def make_signature(assignment: int) -> Callable[[_CorrelationSurface], int]:
        allowed = [branch_paulis[i][(assignment >> i) & 1] for i in range(k)]

        def compute(cs: _CorrelationSurface) -> int:
            bits = cs.bits
            sig = bits & boundary_mask
            for i in range(k):
                sig |= _violation_bit(bits, conditional_bits[i], allowed[i]) << (
                    constraint_shift + i
                )
            return sig

        return compute

    per_assignment_bits: list[int] = []
    for assignment in range(1 << k):
        solution = _solve_in_span(generators, make_signature(assignment), spec_target, space)
        if solution is None:
            resolution = {
                position: (assignment >> i) & 1 for i, position in enumerate(conditional_positions)
            }
            raise TQECError(
                f"The condition of the conditional cube at {conditional_cube_position} cannot "
                "be completed into an evaluable parity when the earlier conditional cubes "
                f"resolve to {resolution}."
            )
        restored = _restore_correlation_surface_from_added_vertices(solution, added_vertices)
        per_assignment_bits.append(restored.bits)

    return _family_from_assignments(
        per_assignment_bits, conditional_positions, space, positioned, source_terms
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


def _presence_bit(bits: int, position: int, allowed: Pauli) -> int:
    """Whether the allowed Pauli strand is present at the half-edge position.

    Only meaningful on surfaces satisfying the closure against ``allowed`` at the position,
    where the other strand is absent (equal for ``Y``).
    """
    if allowed is Pauli.Z:
        return (bits >> (position + 1)) & 1
    return (bits >> position) & 1  # allowed is Pauli.X or Pauli.Y


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
    closure constraints are applied afterwards, per branch assignment for the conditional
    cubes and as coin classification for the initialization leaves.
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


def _time_slice_ordering(graph: BlockGraph, positioned: PositionedZX) -> list[set[int]] | None:
    """Return the time-slice vertex ordering speeding up the search on leafy graphs."""
    if len(graph.leaf_cubes) < _PARTITION_ALONG_TIME_MIN_LEAF_CUBES:
        return None
    time_slices: dict[int, set[int]] = {}
    for position, v in positioned.p2v.items():
        time_slices.setdefault(position.z, set()).add(v)
    if len(time_slices) <= 1:
        return None
    return [time_slices[z] for z in sorted(time_slices)]


def _span_kernel(
    surfaces: Sequence[_CorrelationSurface],
    signature: Callable[[_CorrelationSurface], int],
) -> list[_CorrelationSurface]:
    """Return a spanning set of the combinations of the surfaces with zero signature."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _reform_correlation_surface_generators,
    )

    kernel = _reform_correlation_surface_generators(
        surfaces,
        signature,
        stabilizer_basis={},
        basis_surfaces=[],
        construct_new_surfaces=True,
    )[1]
    return list({cs.bits: cs for cs in kernel if cs.bits}.values())


def _solve_in_span(
    surfaces: Sequence[_CorrelationSurface],
    signature: Callable[[_CorrelationSurface], int],
    target: int,
    space: _CorrelationSurfaceSpace,
) -> _CorrelationSurface | None:
    """Return a combination of the surfaces with the given signature, ``None`` if unreachable."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import (  # noqa: PLC0415
        _CorrelationSurface,
        _solve_linear_system,
        _xor_correlation_surfaces,
    )

    basis: dict[int, tuple[int, int]] = {}
    # the surfaces whose signatures became pivots, aligned with the solution masks
    pivots = [cs for cs in surfaces if _solve_linear_system(basis, signature(cs)) is None]
    indices = _solve_linear_system(basis, target, update_basis=False)
    if indices is None:
        return None
    if not indices:
        return _CorrelationSurface(space)
    return _xor_correlation_surfaces([pivots[i] for i in indices])


def _intersect_spans(u_basis: Sequence[int], v_basis: Sequence[int], width: int) -> list[int]:
    """Basis of the intersection of two GF(2) spans of ``width``-bit vectors (Zassenhaus)."""
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import _solve_linear_system  # noqa: PLC0415

    basis: dict[int, tuple[int, int]] = {}
    for u in u_basis:
        _solve_linear_system(basis, (u << width) | u)
    for v in v_basis:
        _solve_linear_system(basis, v << width)
    return [vector for lead, (vector, _) in basis.items() if lead < width]


def _family_from_assignments(
    per_assignment_bits: list[int],
    conditional_positions: Sequence[Position3D],
    space: _CorrelationSurfaceSpace,
    positioned: PositionedZX,
    source_terms: Sequence[tuple[int, Pauli, Position3D]],
) -> ConditionalCorrelationSurface:
    """Assemble a family from its per-assignment surfaces by a Möbius transform over GF(2).

    ``per_assignment_bits`` holds the surface of each assignment of the condition bits of
    ``conditional_positions``, indexed by the assignment as a bit mask. The Möbius (zeta)
    transform turns them into the algebraic normal form: the delta of a subset ``T`` is the
    XOR of the surfaces of the assignments below ``T``.
    """
    # Needs to be imported here to avoid pulling pyzx when importing this module.
    from tqec.computation._correlation import _CorrelationSurface  # noqa: PLC0415

    k = len(conditional_positions)
    assert len(per_assignment_bits) == 1 << k
    anf = list(per_assignment_bits)
    for i in range(k):
        bit = 1 << i
        for b in range(1 << k):
            if b & bit:
                anf[b] ^= anf[b ^ bit]
    base = _CorrelationSurface(space, anf[0]).to_immutable_public_representation(positioned)
    deltas = tuple(
        (
            frozenset(conditional_positions[i] for i in range(k) if (subset >> i) & 1),
            _CorrelationSurface(space, anf[subset]).to_immutable_public_representation(positioned),
        )
        for subset in range(1, 1 << k)
        if anf[subset]
    )
    coins = frozenset(
        position
        for pos, matched, position in source_terms
        if _violation_bit(per_assignment_bits[0], pos, matched)
    )
    return ConditionalCorrelationSurface(base, deltas, coins)


def _family_sort_key(family: ConditionalCorrelationSurface) -> tuple[Any, ...]:
    """Canonical sort key for the returned families."""
    return (
        tuple(sorted(family.base.span)),
        tuple(
            (
                tuple(sorted(p.as_tuple() for p in positions)),
                tuple(sorted(delta.span)),
            )
            for positions, delta in family.deltas
        ),
    )
