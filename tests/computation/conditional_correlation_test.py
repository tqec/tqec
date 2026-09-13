"""Tests for the branch-resolvable correlation surfaces of conditional computations."""

from itertools import combinations, pairwise, product
from typing import Any

import pytest

from tqec.computation import _correlation
from tqec.computation._gf2 import _solve_parity_constraints
from tqec.computation.block_graph import BlockGraph
from tqec.computation.conditional import (
    ConditionalCorrelationSurface,
    ConditionalCubeConstraint,
    complete_surfaces,
)
from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.interop.pyzx.positioned import PositionedZX
from tqec.interop.pyzx.utils import zx_to_pauli
from tqec.utils.enums import Basis, Pauli
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def _surface(
    *edges: tuple[tuple[int, int, int], tuple[int, int, int], Basis],
) -> CorrelationSurface:
    return CorrelationSurface(
        frozenset(
            ZXEdge(ZXNode(Position3D(*u), basis), ZXNode(Position3D(*v), basis))
            for u, v, basis in edges
        )
    )


def _bit(tag: int = 0) -> ConditionalCorrelationSurface:
    """Build a distinct completed condition, i.e. the identity of one classical bit.

    Hand-constructed constraints still need a bit identity; the surface itself is irrelevant to
    the GF(2) resolution under test, only its distinctness from other bits matters.
    """
    return ConditionalCorrelationSurface(
        particular=_surface(((0, 0, tag), (0, 0, tag + 1), Basis.X))
    )


def _in_gf2_span(surface: CorrelationSurface, generators: list[CorrelationSurface]) -> bool:
    """Whether the surface is a XOR combination of the generators (small test graphs only)."""
    spans = [g.span for g in generators]
    for r in range(len(spans) + 1):
        for combo in combinations(spans, r):
            combined: frozenset[ZXEdge] = frozenset()
            for span in combo:
                combined = combined.symmetric_difference(span)
            if combined == surface.span:
                return True
    return False


def _resolve_or_none(
    completed: ConditionalCorrelationSurface, condition_values: int | dict[Position3D, int]
) -> CorrelationSurface | None:
    """Resolve the surface, or return None if the branch assignment has no valid resolution."""
    try:
        return completed.resolve(condition_values)
    except TQECError:
        return None


def _obeys_spider_rules(surface: CorrelationSurface, graph: BlockGraph) -> bool:
    """Whether the surface is a valid correlation surface of a graph without conditional cubes.

    Checks the local rule of every spider directly: a Z (X) spider broadcasts the X (Z) component
    of the surface identically onto every incident half-edge and passes the Z (X) component
    through in pairs. On a leaf that is exactly the closure rule -- the surface terminates
    commuting with the leaf -- so this also certifies that a completion collects only records that
    exist. Ports are open and absorb anything.

    Unlike :func:`_in_gf2_span` this needs no reference search, and accepts the surfaces that
    :func:`~tqec.computation.correlation.find_correlation_surfaces` normalizes away, i.e. those
    differing from a returned generator by a surface closed on every open leaf.
    """
    positioned = PositionedZX.from_block_graph(graph)
    zx_graph = positioned.g
    half_edges: dict[tuple[Position3D, Position3D], Pauli] = {}
    for edge in surface.span:
        for near, far in ((edge.u, edge.v), (edge.v, edge.u)):
            key = (near.position, far.position)
            half_edges[key] = half_edges.get(key, Pauli.I) ^ near.basis.to_pauli()
    for v in zx_graph.vertices():
        basis = zx_to_pauli(zx_graph, v)
        paulis = [
            half_edges.get((positioned[v], positioned[n]), Pauli.I) for n in zx_graph.neighbors(v)
        ]
        if basis is Pauli.I:  # an open port terminates anything
            continue
        if basis is Pauli.Y:  # a magic state leaf absorbs Y only
            if paulis[0] not in (Pauli.I, Pauli.Y):
                return False
            continue
        if len({pauli & basis.flipped() for pauli in paulis}) > 1:  # broadcast
            return False
        if sum(bool(pauli & basis) for pauli in paulis) % 2:  # passthrough parity
            return False
    return True


def _merge_then_conditional_graph(extend_data: bool = True) -> BlockGraph:
    """Build a Z memory column merged with an ancilla measured in a conditional basis.

    Neither variant admits an evaluable merge-outcome condition. With ``extend_data`` the
    memory column continues past the merge into the future, so the only completion of the
    condition runs the membrane onto that parallel worldline -- a future, yet-unmeasured
    logical operator rather than a past record. Without it the column is measured before the
    conditional cube's time slice, leaving the only membrane terminating anticommuting on the
    Z initialization. Both are rejected: static leaves are closed and a condition must close
    entirely within the strict past.
    """
    g = BlockGraph("conditional measurement")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(
        Position3D(1, 0, 2),
        "ZXZ_ZXX",
        condition=_surface(((0, 0, 1), (1, 0, 1), Basis.X)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    if extend_data:
        g.add_cube(Position3D(0, 0, 2), "ZXZ")
        g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.validate()
    return g


def _magic_merge_graph() -> BlockGraph:
    """Build a magic-state injection onto a fresh Z-basis initialization, then conditional.

    The magic state preparation is an open port on the left column; the data on the right
    column is a fresh Z-basis initialization leaf at ``(1, 0, 0)`` -- a known stabilizer
    state. The X-basis merge anticommutes with that ``Z`` stabilizer, so the merge outcome
    (the conditional cube's condition) is a classically samplable stabilizer coin independent
    of the magic state. This is the simplifiable "T injection onto a known stabilizer state"
    case: the condition has no strict-past completion, so it is rejected -- both when completed
    directly and when reached as the classical bit of an observable depending on the cube.
    """
    g = BlockGraph("magic merge")
    g.add_cube(Position3D(0, 0, 0), "PORT", "magic_in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(
        Position3D(1, 0, 2),
        "ZXZ_ZXX",
        condition=_surface(((0, 0, 1), (1, 0, 1), Basis.X)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()
    return g


def _injection_on_unknown_data_graph() -> BlockGraph:
    """Build a magic-state injection onto an unknown (ported) data qubit, then conditional.

    Both the magic ancilla ``(0, 0, 0)`` and the data qubit ``(1, 0, 0)`` enter as open ports,
    so neither column is a known stabilizer state. The merge outcome (the condition) is then a
    genuine port-sourced parity, not a classically samplable coin, and its completion closes
    entirely within the strict past by terminating at the two ports -- never on the conditional
    cube's own interface. This is the legitimate T-injection case in which the conditional
    correction is actually needed.
    """
    g = BlockGraph("injection on unknown data")
    g.add_cube(Position3D(0, 0, 0), "PORT", "magic_in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "PORT", "data_in")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(
        Position3D(1, 0, 2),
        "ZXZ_ZXX",
        condition=_surface(((0, 0, 1), (1, 0, 1), Basis.X)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()
    return g


def _route_around_graph(condition_basis: Basis = Basis.Z) -> BlockGraph:
    """Build a closed memory column with a spatial conditional cube hanging off its middle."""
    g = BlockGraph("route around")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "ZXZ")  # sideways leaf: measurement face exposed
    g.add_cube(Position3D(0, 0, 1), "ZXX")  # Z-spider hub: Z strands pass through in pairs
    g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_cube(
        Position3D(0, 1, 1),
        "ZXX_ZZX",
        condition=_surface(((0, 0, 0), (1, 0, 0), condition_basis)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 1, 1))
    g.validate()
    return g


def _chained_condition_graph(with_alternative_route: bool) -> BlockGraph:
    """Build two stacked conditional cubes, the later condition optionally crossing the earlier.

    Both columns start from open ports, so both conditions close on arbitrary prior states
    rather than on known stabilizer initializations: the earlier cube's merge parity terminates
    at the ``aux`` port and is a genuine record parity. The two cubes therefore read *different*
    classical bits.

    Without the alternative route, the later cube's condition is pinned on the earlier cube's own
    interface, so its only completion terminates with X on the earlier conditional cube -- invalid
    when that cube resolves to its Z-measurement branch. With the alternative route, the later
    cube reads the same merge parity as the earlier one, which closes at the ports without
    touching the earlier cube.
    """
    g = BlockGraph("chained conditions")
    early_condition = _surface(((0, 0, 1), (1, 0, 1), Basis.X))
    late_condition = (
        early_condition if with_alternative_route else _surface(((1, 0, 1), (1, 0, 2), Basis.X))
    )
    g.add_cube(Position3D(0, 0, 0), "PORT", "in")
    g.add_cube(Position3D(1, 0, 0), "PORT", "aux")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_cube(Position3D(0, 0, 3), "ZXZ_ZXX", condition=late_condition)
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 2), "ZXZ_ZXX", condition=early_condition)
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(0, 0, 2), Position3D(0, 0, 3))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()
    return g


def _shared_bit_graph() -> BlockGraph:
    """Build two conditional measurement columns whose cubes share one condition bit.

    Both columns start from open ports representing arbitrary prior states, so the shared merge
    parity is a genuine record parity that completes on the strict past rather than a samplable
    stabilizer coin. The two cubes carry the same condition and read one classical bit.
    """
    g = BlockGraph("shared bit")
    condition = _surface(((0, 0, 1), (1, 0, 1), Basis.X))
    g.add_cube(Position3D(0, 0, 0), "PORT", "a_in")
    g.add_cube(Position3D(1, 0, 0), "PORT", "b_in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "ZXZ_ZXX", condition=condition)
    g.add_cube(Position3D(1, 0, 2), "ZXZ_ZXX", condition=condition)
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()
    return g


def _auto_corrected_t_injections_graph(num_injections: int) -> BlockGraph:
    """Build a data column receiving consecutive auto-corrected T injections.

    The data column runs from the ``data_in`` port to the ``data_out`` port through one ``ZXX``
    cube per injection, at ``(0, 0, 1)``, ``(0, 0, 2)``, ... Each injection merges the data cube
    with a magic patch on alternating sides, entering from its own magic port one time slice
    earlier, in a ``ZZ`` merge; the magic patch is then measured by an ``X``-or-``Y`` conditional
    cube whose condition is the merge outcome.
    """
    g = BlockGraph("auto-corrected T injections")
    data = [Position3D(0, 0, z) for z in range(num_injections + 2)]
    g.add_cube(data[0], "PORT", "data_in")
    g.add_cube(data[-1], "PORT", "data_out")
    for data_merge in data[1:-1]:
        g.add_cube(data_merge, "ZXX")
    for u, v in pairwise(data):
        g.add_pipe(u, v)
    for index, data_merge in enumerate(data[1:-1]):
        magic_merge = data_merge.shift_by(dy=1 if index % 2 == 0 else -1)
        magic_in, magic_measurement = magic_merge.shift_by(dz=-1), magic_merge.shift_by(dz=1)
        g.add_cube(magic_in, "PORT", f"magic_{index}")
        g.add_cube(magic_merge, "ZXX")
        g.add_cube(
            magic_measurement,
            "ZXX_Y",
            condition=_surface((data_merge.as_tuple(), magic_merge.as_tuple(), Basis.Z)),
        )
        g.add_pipe(magic_in, magic_merge)
        g.add_pipe(data_merge, magic_merge)
        g.add_pipe(magic_merge, magic_measurement)
    g.validate()
    return g


def test_resolve_solves_the_selected_closure_rows() -> None:
    p = Position3D(0, 0, 1)
    g0 = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    g1 = _surface(((0, 0, 0), (0, 0, 1), Basis.X))
    surface = ConditionalCorrelationSurface(
        particular=g0,
        kernel=(g0 ^ g1,),
        # branch 0 is satisfied by the particular surface; branch 1 needs the kernel element
        # XORed in, turning g0 into g1.
        constraints=(
            ConditionalCubeConstraint(frozenset({p}), (((0b0, 0),), ((0b1, 1),)), _bit()),
        ),
    )
    assert surface.dependencies == {p}
    assert surface.resolve(0) == g0
    assert surface.resolve({p: 1}) == g1
    with pytest.raises(KeyError):
        surface.resolve({})


def test_resolve_raises_on_inconsistent_branch() -> None:
    p = Position3D(0, 0, 1)
    generator = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    surface = ConditionalCorrelationSurface(
        particular=generator,
        constraints=(
            ConditionalCubeConstraint(frozenset({p}), (((0b0, 0),), ((0b0, 1),)), _bit()),
        ),
    )
    assert surface.resolve(0) == generator
    with pytest.raises(TQECError, match="no valid resolution"):
        surface.resolve(1)


def test_solve_parity_constraints() -> None:
    # Two independent, consistent rows over two kernel coordinates: c0 = 0 (parity of {c0} is
    # 0) and c1 = 1 (parity of {c1} is 1), so the unique solution is 0b10.
    assert _solve_parity_constraints([(0b01, 0), (0b10, 1)], 2) == 0b10
    # Free coordinates are set to zero: only c1 is pinned to 1.
    assert _solve_parity_constraints([(0b10, 1)], 2) == 0b10
    # Empty and trivially-satisfied systems are consistent with the zero combination.
    assert _solve_parity_constraints([], 2) == 0
    assert _solve_parity_constraints([(0b00, 0)], 2) == 0
    # Conflicting rows on the same coordinate are inconsistent.
    assert _solve_parity_constraints([(0b1, 0), (0b1, 1)], 1) is None
    # A row demanding parity 1 from no coordinates (0 == 1) is inconsistent.
    assert _solve_parity_constraints([(0b0, 1)], 1) is None


def test_jointly_consistent_constraints_resolve_branch_invariantly() -> None:
    # When one kernel combination satisfies every branch of every constraint, the resolved
    # surface is the same in all branches: this is the branch-invariance that lets the compiler
    # fold the combination into ``particular`` and drop the runtime system entirely.
    p0, p1 = Position3D(0, 0, 1), Position3D(1, 0, 1)
    g0 = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    g1 = _surface(((0, 0, 0), (0, 0, 1), Basis.X))
    # Both branches of both cubes are satisfied by the single combination 0b1 (XOR the one
    # kernel element into the particular surface), regardless of the resolved bits.
    surface = ConditionalCorrelationSurface(
        particular=g0,
        kernel=(g0 ^ g1,),
        constraints=(
            ConditionalCubeConstraint(frozenset({p0}), (((0b1, 1),), ((0b1, 1),)), _bit(0)),
            ConditionalCubeConstraint(frozenset({p1}), (((0b1, 1),), ((0b1, 1),)), _bit(2)),
        ),
    )
    resolved = {(b0, b1): surface.resolve({p0: b0, p1: b1}) for b0 in (0, 1) for b1 in (0, 1)}
    assert set(resolved.values()) == {g1}


def test_shared_bit_agreement_and_invariants() -> None:
    p0, p1 = Position3D(0, 0, 1), Position3D(1, 0, 1)
    generator = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    # One classical bit wired to two cubes is a single constraint over both positions.
    surface = ConditionalCorrelationSurface(
        particular=generator,
        constraints=(ConditionalCubeConstraint(frozenset({p0, p1}), ((), ()), _bit()),),
    )
    assert surface.dependencies == {p0, p1}
    assert surface.resolve({p0: 1, p1: 1}) == generator
    with pytest.raises(TQECError, match="share one condition bit"):
        surface.resolve({p0: 0, p1: 1})
    # A position may not belong to two bits, and a constraint must wire at least one position.
    with pytest.raises(TQECError, match="single bit"):
        ConditionalCorrelationSurface(
            particular=generator,
            constraints=(
                ConditionalCubeConstraint(frozenset({p0}), ((), ()), _bit(0)),
                ConditionalCubeConstraint(frozenset({p0, p1}), ((), ()), _bit(2)),
            ),
        )
    with pytest.raises(TQECError, match="at least one position"):
        ConditionalCorrelationSurface(
            particular=generator,
            constraints=(ConditionalCubeConstraint(frozenset(), ((), ()), _bit()),),
        )


def test_dict_round_trip() -> None:
    completed = _injection_on_unknown_data_graph().complete_condition(Position3D(1, 0, 2))
    assert ConditionalCorrelationSurface.from_dict(completed.to_dict()) == completed


def test_find_correlation_surfaces_raises_on_conditional_graph() -> None:
    g = _merge_then_conditional_graph()
    with pytest.raises(TQECError, match="complete_observable_surfaces"):
        g.find_correlation_surfaces()


def test_complete_observable_on_static_graph() -> None:
    g = BlockGraph("memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    assert completed.constraints == ()
    assert completed.dependencies == frozenset()
    assert completed.resolve(0) == completed.resolve(1)
    assert completed.resolve(0) == _surface(((0, 0, 0), (0, 0, 1), Basis.Z))


def test_route_around_observable_on_closed_graph() -> None:
    # The Z tube through the Z-spider hub avoids the conditional cube entirely and resolves
    # to the same deterministic observable in both branches. It is recovered because it is
    # non-trivial at the cut-edge boundary (it realizes the Z spec there), so it is never a
    # closed surface and is never at risk of being dropped by the search normalization.
    g = _route_around_graph()
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    # The observable never touches the conditional cube, so its closure is trivially satisfied
    # in both branches: the cube is dropped as a dependency and the surface collapses to one
    # fixed completion with no runtime system.
    assert completed.dependencies == frozenset()
    assert completed.constraints == ()
    assert completed.kernel == ()
    expected = _surface(
        ((0, 0, 0), (1, 0, 0), Basis.Z),
        ((0, 0, 0), (0, 0, 1), Basis.Z),
        ((0, 0, 1), (0, 0, 2), Basis.Z),
    )
    for value in (0, 1):
        assert completed.resolve(value) == expected
        resolved_graph = g.resolve_conditional_kinds(value)
        assert _in_gf2_span(completed.resolve(value), resolved_graph.find_correlation_surfaces())


def test_observable_with_ports_resolves_per_branch() -> None:
    # The ancilla column starts from an open port ("aux") representing an arbitrary prior state,
    # so the cube's merge-outcome condition is a genuine record parity that completes on its
    # strict past rather than a samplable stabilizer coin.
    g = BlockGraph("open with conditional")
    g.add_cube(Position3D(0, 0, 0), "PORT", "in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "PORT", "out")
    g.add_cube(Position3D(1, 0, 0), "PORT", "aux")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(
        Position3D(1, 0, 2),
        "ZXZ_ZXX",
        condition=_surface(((0, 0, 1), (1, 0, 1), Basis.X)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()
    # ``ordered_ports`` is ("aux", "in", "out"), so the external stabilizers below read in that
    # order: the X flow does not touch the ancilla port, the Z flow does.
    assert g.ordered_ports == ["aux", "in", "out"]

    # The X flow from port to port avoids the conditional cube and resolves identically in
    # both branches, with the same external stabilizer.
    (x_flow,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.X))])
    assert x_flow.dependencies == frozenset()
    for value in (0, 1):
        resolved = x_flow.resolve(value)
        assert resolved.external_stabilizer_on_graph(g) == "IXX"
        assert _in_gf2_span(
            resolved, g.resolve_conditional_kinds(value).find_correlation_surfaces()
        )

    # The Z flow spreads onto the merged ancilla and terminates on the conditional cube: it
    # only closes in the ZXZ branch. Compile-time completion succeeds (runtime-only
    # validation), and the unsolvable branch is reported by resolve().
    (z_flow,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    resolved = z_flow.resolve(0)
    assert resolved.external_stabilizer_on_graph(g) == "ZZZ"
    assert Position3D(1, 0, 2) in resolved.positions
    with pytest.raises(TQECError, match="no valid resolution"):
        z_flow.resolve(1)


def test_stabilizer_random_observable_cannot_be_completed() -> None:
    # Z-basis initialization followed by an X-basis measurement: the readout bit is a
    # uniformly random logical bit sourced purely by stabilizer randomness. With static
    # leaves closed, no completion exists: nondeterministic observables must terminate at
    # ports (e.g. magic state preparations) instead.
    g = BlockGraph("coin readout")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.validate()
    spec = _surface(((0, 0, 0), (0, 0, 1), Basis.X))

    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_observable_surfaces([spec])


def test_complete_condition_extending_onto_parallel_worldline_raises() -> None:
    # The merge-outcome condition can only close by running the X membrane along the memory
    # column, which continues past the conditional cube's time slice into the future. That
    # parallel worldline is a yet-unmeasured logical operator, not a past record, so the
    # completion is forbidden from extending onto it and no valid condition surface exists:
    # a condition must close entirely within the strict past.
    g = _merge_then_conditional_graph(extend_data=True)
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(1, 0, 2))


def test_complete_condition_without_future_escape_raises() -> None:
    # When the memory column is measured before the conditional cube's time slice, the only
    # membrane for the merge outcome terminates anticommuting on the Z initialization, which
    # is not evaluable-representable: static leaves are closed.
    g = _merge_then_conditional_graph(extend_data=False)
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(1, 0, 2))


def test_complete_condition_of_injection_onto_stabilizer_state_raises() -> None:
    # The data column is a fresh Z initialization -- a known stabilizer state -- and the
    # X merge anticommutes with it, so the merge outcome is a classically samplable stabilizer
    # coin, not a magic-sourced parity. The only completion terminating in the strict past
    # would anticommute on that Z initialization; the alternative, riding the X strand up onto
    # the conditional cube's own (not-yet-fired) interface, is forbidden because the condition
    # must be evaluable before the cube fires. This is the simplifiable T-injection-onto-a-
    # stabilizer-state case: the condition is rejected.
    g = _magic_merge_graph()
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(1, 0, 2))


def test_complete_condition_of_injection_onto_unknown_data_closes_in_past() -> None:
    # A legitimate T injection: the data qubit is unknown (an open port), so the merge outcome
    # is a genuine port-sourced parity rather than a stabilizer coin. The condition membrane
    # closes entirely within the strict past by terminating at the two ports (magic ancilla and
    # data input), never touching the conditional cube's own interface.
    g = _injection_on_unknown_data_graph()
    completed = g.complete_condition(Position3D(1, 0, 2))
    assert completed.constraints == ()
    assert completed.resolve(0) == _surface(
        ((0, 0, 0), (0, 0, 1), Basis.X),
        ((0, 0, 1), (1, 0, 1), Basis.X),
        ((1, 0, 0), (1, 0, 1), Basis.X),
    )
    # Every position of the completion lies strictly before the conditional cube's time slice:
    # the condition is evaluable from past records and port sources alone.
    assert all(p.z < 2 for p in completed.resolve(0).positions)


def test_nondeterministic_observable_routes_to_magic_port() -> None:
    # The observable rides the merge up onto the conditional cube: it terminates on the cube,
    # whose X-measurement branch is the only solvable one, and routes its randomness back to the
    # magic port. Which port it routes to is a genuine choice here -- the X strand may pair
    # sideways through the merge to the magic ancilla or straight down to the data input -- and the
    # unpinned choice is settled by an arbitrary reference completion, so the spec pins the magic
    # pipe to select the magic-sourced class. ``ordered_ports`` is ("data_in", "magic_in"), so
    # "IX" is support on the magic port alone.
    g = _injection_on_unknown_data_graph()
    assert g.ordered_ports == ["data_in", "magic_in"]
    (completed,) = g.complete_observable_surfaces(
        [_surface(((1, 0, 1), (1, 0, 2), Basis.X), ((0, 0, 0), (0, 0, 1), Basis.X))]
    )
    assert completed.dependencies == {Position3D(1, 0, 2)}
    resolved = completed.resolve(1)
    assert resolved.external_stabilizer_on_graph(g) == "IX"
    assert Position3D(0, 0, 0) in resolved.positions
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(0)

    # Left to the reference completion, the spec on the merge alone still resolves to a valid
    # observable of the resolved computation, in whichever class the reference lands.
    (unpinned,) = g.complete_observable_surfaces([_surface(((1, 0, 1), (1, 0, 2), Basis.X))])
    assert unpinned.dependencies == {Position3D(1, 0, 2)}
    assert _in_gf2_span(
        unpinned.resolve(1), g.resolve_conditional_kinds(1).find_correlation_surfaces()
    )


@pytest.mark.parametrize("num_injections", [1, 2])
def test_auto_corrected_t_injection_observable_resolves_in_every_branch(
    num_injections: int,
) -> None:
    # In branch ``c`` the merges and magic measurements fuse into a single Z spider of phase
    # ``(c_0 + c_1 + ...) pi/2`` joining the data and magic ports. The X observable at the output
    # is valid in every branch, but with an odd number of Y-basis measurements it must carry Y on
    # some port instead of X: the Z strands leaving the Y half cubes cannot all pair up with each
    # other, so one closes at a port. Its port Paulis therefore genuinely differ per branch, so
    # they must not be pinned across the branches, which would make those branches unsolvable.
    g = _auto_corrected_t_injections_graph(num_injections)
    cubes = sorted((cube.position for cube in g.conditional_cubes), key=lambda p: p.z)
    (x_observable,) = g.complete_observable_surfaces(
        [_surface(((0, 0, num_injections), (0, 0, num_injections + 1), Basis.X))]
    )
    assert x_observable.dependencies == set(cubes)
    for values in product((0, 1), repeat=num_injections):
        assignment = dict(zip(cubes, values))
        resolved = x_observable.resolve(assignment)
        assert _obeys_spider_rules(resolved, g.resolve_conditional_kinds(assignment))
        if sum(values) % 2 == 1:
            assert "Y" in resolved.external_stabilizer_on_graph(g)


def test_observable_depending_on_a_samplable_coin_cube_raises() -> None:
    # The conditional cube's condition is a stabilizer coin (the X merge onto a known Z
    # initialization), so it has no completion into a parity of records. An observable that
    # genuinely depends on that cube would need the coin as a classical bit, so it is rejected
    # rather than represented: the structure is either purely Clifford or admits a
    # simplification in which the condition is not needed.
    g = _magic_merge_graph()
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_observable_surfaces([_surface(((0, 0, 1), (1, 0, 1), Basis.X))])


def test_complete_condition_of_route_around_extends_into_future_raises() -> None:
    # The declared condition of the route-around graph reads the sideways leaf's Z, but the
    # only membrane carrying it runs up the memory column and across the cut into the future
    # (the column continues past the conditional cube's time slice). The condition would then
    # depend on a future logical operator rather than on past records, so it is rejected.
    g = _route_around_graph(condition_basis=Basis.Z)
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(0, 1, 1))


def test_complete_condition_anticommuting_measurement_leaf_raises() -> None:
    # An X strand pinned on the merge with the sideways leaf is unevaluable: the leaf's
    # exposed face is a Z-basis measurement, and X records do not exist there. Static leaves
    # are closed, so the completion fails at compile time.
    g = _route_around_graph(condition_basis=Basis.X)
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(0, 1, 1))


def test_complete_condition_on_static_cube_raises() -> None:
    g = _merge_then_conditional_graph()
    with pytest.raises(TQECError, match="not a conditional cube"):
        g.complete_condition(Position3D(0, 0, 0))


def test_chained_condition_unsolvable_branch_raises_at_resolve() -> None:
    # The completion of the later condition is forced onto the earlier conditional cube with
    # an X termination. Compile-time completion succeeds; the Z branch of the earlier cube
    # is reported as unsolvable at resolution time.
    g = _chained_condition_graph(with_alternative_route=False)
    earlier = Position3D(1, 0, 2)
    completed = g.complete_condition(Position3D(0, 0, 3))
    assert completed.dependencies == {earlier}
    resolved = completed.resolve({earlier: 1})
    assert resolved.bases_at(earlier) == {Basis.X}
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve({earlier: 0})


def test_chained_condition_resolves_per_branch() -> None:
    g = _chained_condition_graph(with_alternative_route=True)
    earlier = Position3D(1, 0, 2)
    completed = g.complete_condition(Position3D(0, 0, 3))
    assert completed.dependencies <= {earlier}
    spec_edge = ZXEdge(ZXNode(Position3D(0, 0, 1), Basis.X), ZXNode(Position3D(1, 0, 1), Basis.X))
    for value in (0, 1):
        resolved = completed.resolve({earlier: value})
        # the resolution contains the user-specified partial surface
        assert spec_edge in resolved.span
        # and satisfies the closure of the resolved branch at the earlier conditional cube:
        # Z-measurement (value 0) absorbs only Z strands, X-measurement (value 1) only X.
        allowed = Basis.Z if value == 0 else Basis.X
        if earlier in resolved.positions:
            assert resolved.bases_at(earlier) <= {allowed}


def test_conflicting_cubes_over_one_kernel_coordinate_do_not_collapse() -> None:
    # A port-terminated observable on the chained graph touches both conditional cubes over a
    # single shared kernel coordinate: the spec pins both ports, leaving one free combination.
    # In branch 0 both cubes require that coordinate to vanish, while in branch 1 the particular
    # surface violates both cubes and no kernel combination repairs it, so no single combination
    # satisfies every branch and the surface must NOT collapse: both cubes remain genuine
    # dependencies. This exercises the joint-consistency check over a real (width-1) kernel with
    # several conditional cubes, guarding against over-eager collapsing.
    g = _chained_condition_graph(with_alternative_route=False)
    early, late = Position3D(1, 0, 2), Position3D(0, 0, 3)
    (completed,) = g.complete_observable_surfaces(
        [_surface(((0, 0, 0), (0, 0, 1), Basis.Z), ((1, 0, 0), (1, 0, 1), Basis.Z))]
    )
    assert completed.dependencies == {early, late}
    assert len(completed.kernel) == 1
    # The two cubes carry different conditions, which complete to different record parities, so
    # they read two distinct classical bits and stay two separate constraints.
    by_position = {min(c.positions): c for c in completed.constraints}
    assert set(by_position) == {early, late}
    assert by_position[early].condition != by_position[late].condition
    # Bit value 1 selects the conflicting branch rows and is unsolvable; value 0 is fine.
    assert completed.resolve(0) is not None
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(1)


def test_shared_condition_bits_are_grouped() -> None:
    g = _shared_bit_graph()
    p0, p1 = Position3D(0, 0, 2), Position3D(1, 0, 2)
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    # The two cubes' conditions complete to the same record parity, so they read one classical
    # bit and collapse into a single constraint over both positions, keyed by that completed
    # condition -- the handle lowering joins to the OBSERVABLE_INCLUDE realizing the parity.
    assert len(completed.constraints) == 1
    assert completed.constraints[0].positions == frozenset({p0, p1})
    assert completed.constraints[0].condition == g.complete_condition(p0)
    assert completed.constraints[0].condition == g.complete_condition(p1)
    # The Z membrane spreads across the merge and terminates on both conditional cubes: it
    # closes when the shared bit selects the Z branches, and fails when it selects X.
    resolved = completed.resolve(0)
    assert resolved.bases_at(p0) == {Basis.Z}
    assert resolved.bases_at(p1) == {Basis.Z}
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(1)
    with pytest.raises(TQECError, match="share one condition bit"):
        completed.resolve({p0: 0, p1: 1})


def test_one_sweep_backs_every_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every completion on a graph is read off one correlation surface sweep: the observable is
    # completed on its last stage and each condition on the stage holding its strict past, so
    # neither the number of observables nor the number of conditions reached adds a search.
    sweeps = 0
    sweep = _correlation._sweep_correlation_surface_generators

    def counting_sweep(*args: Any, **kwargs: Any) -> Any:
        nonlocal sweeps
        sweeps += 1
        return sweep(*args, **kwargs)

    monkeypatch.setattr(_correlation, "_sweep_correlation_surface_generators", counting_sweep)
    g = _chained_condition_graph(with_alternative_route=False)
    early, late = Position3D(1, 0, 2), Position3D(0, 0, 3)
    observables, conditions = complete_surfaces(
        g,
        [_surface(((0, 0, 0), (0, 0, 1), Basis.Z)), _surface(((0, 0, 0), (0, 0, 1), Basis.X))],
        [early, late],
    )
    # Both cubes are genuine dependencies of the Z flow, so both conditions were completed, and
    # completing the later one recursed into the earlier one's bit.
    assert len(observables[0].constraints) == 2
    assert sweeps == 1
    # and the shared sweep completes them exactly as a dedicated search would
    assert conditions[late] == g.complete_condition(late)
    assert conditions[early] == g.complete_condition(early)


@pytest.mark.parametrize(
    ("graph", "spec", "values"),
    [
        (_shared_bit_graph(), ((0, 0, 0), (0, 0, 1), Basis.Z), (0,)),
        (_shared_bit_graph(), ((1, 0, 0), (1, 0, 1), Basis.X), (0, 1)),
        (
            _chained_condition_graph(with_alternative_route=True),
            ((0, 0, 0), (0, 0, 1), Basis.Z),
            (0,),
        ),
        (
            _chained_condition_graph(with_alternative_route=True),
            ((0, 0, 0), (0, 0, 1), Basis.X),
            (0, 1),
        ),
        (_injection_on_unknown_data_graph(), ((1, 0, 1), (1, 0, 2), Basis.X), (1,)),
    ],
)
def test_completions_are_correlation_surfaces_of_the_resolved_graph(
    graph: BlockGraph,
    spec: tuple[tuple[int, int, int], tuple[int, int, int], Basis],
    values: tuple[int, ...],
) -> None:
    # The specs of every observable and of every condition share one cut set, so a completion
    # must pin the cut edges it does not specify to be consistent across the cut: the generators
    # resolve the two halves of a cut independently, and an unpinned cut edge would let a
    # combination that is not a correlation surface of the uncut graph through. Check the local
    # spider rules of every resolution on the statically resolved computation, which is exactly
    # what such an inconsistency would break.
    (completed,) = graph.complete_observable_surfaces([_surface(spec)])
    for value in values:
        resolved_graph = graph.resolve_conditional_kinds(value)
        assert _obeys_spider_rules(completed.resolve(value), resolved_graph)
        for constraint in completed.constraints:
            # A condition is evaluated before its cube fires, but it is a surface of the whole
            # computation all the same: identity beyond the causal cut satisfies every rule there.
            assert _obeys_spider_rules(constraint.condition.resolve(value), resolved_graph)


def test_sharing_the_sweep_does_not_change_a_completion() -> None:
    # Completing several observables in one call cuts every spec into the one searched graph, so a
    # completion is done over a finer generating set than when it is completed alone. Its kernel
    # coordinates, and which of several equally valid surfaces a branch picks, may therefore
    # differ, but not its dependencies nor which branches are solvable.
    g = _shared_bit_graph()
    specs = [_surface(((0, 0, 0), (0, 0, 1), Basis.Z)), _surface(((1, 0, 0), (1, 0, 1), Basis.X))]
    joint = g.complete_observable_surfaces(specs)
    for spec, completed in zip(specs, joint):
        (alone,) = g.complete_observable_surfaces([spec])
        assert alone.dependencies == completed.dependencies
        for value in (0, 1):
            resolutions = [_resolve_or_none(alone, value), _resolve_or_none(completed, value)]
            if resolutions[0] is None or resolutions[1] is None:
                assert resolutions == [None, None]
                continue
            resolved_graph = g.resolve_conditional_kinds(value)
            assert all(_obeys_spider_rules(s, resolved_graph) for s in resolutions)
