"""Tests for the branch-resolvable correlation surfaces of conditional computations."""

from itertools import combinations

import pytest

from tqec.computation._gf2 import _solve_parity_constraints
from tqec.computation.block_graph import BlockGraph
from tqec.computation.conditional import (
    ConditionalCorrelationSurface,
    ConditionalCubeConstraint,
)
from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.utils.enums import Basis
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
    case: as a *condition* it has no strict-past completion and is rejected. As an
    *observable*, though, the magic-sourced X flow ``X_A = m·r`` from the port to the cube is a
    legitimate nondeterministic observable (no strict-past requirement).
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
    """Build two stacked conditional cubes with the later condition crossing the earlier one.

    The base of the memory column is an open port, so X strands may terminate there. Without
    the alternative route through the X-basis initialization at ``(1, 0, 0)``, the only
    completion of the later condition terminates with X on the earlier conditional cube,
    which is invalid when that cube resolves to its Z-measurement branch.
    """
    g = BlockGraph("chained conditions")
    condition = _surface(((0, 0, 1), (1, 0, 1), Basis.X))
    g.add_cube(Position3D(0, 0, 0), "PORT", "in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "ZXZ")
    g.add_cube(Position3D(0, 0, 3), "ZXZ_ZXX", condition=condition)
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(Position3D(1, 0, 2), "ZXZ_ZXX", condition=condition)
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(0, 0, 2), Position3D(0, 0, 3))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    if with_alternative_route:
        g.add_cube(Position3D(1, 0, 0), "ZXX")
        g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
    g.validate()
    return g


def _shared_bit_graph() -> BlockGraph:
    """Build two conditional measurement columns whose cubes share one condition bit."""
    g = BlockGraph("shared bit")
    condition = _surface(((0, 0, 0), (1, 0, 0), Basis.X))
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(1, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ_ZXX", condition=condition)
    g.add_cube(Position3D(1, 0, 1), "ZXZ_ZXX", condition=condition)
    g.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(1, 0, 0), Position3D(1, 0, 1))
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
        constraints=(ConditionalCubeConstraint(p, ((0b0, 0), (0b1, 1))),),
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
        constraints=(ConditionalCubeConstraint(p, ((0b0, 0), (0b0, 1))),),
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
            ConditionalCubeConstraint(p0, ((0b1, 1), (0b1, 1))),
            ConditionalCubeConstraint(p1, ((0b1, 1), (0b1, 1))),
        ),
    )
    resolved = {(b0, b1): surface.resolve({p0: b0, p1: b1}) for b0 in (0, 1) for b1 in (0, 1)}
    assert set(resolved.values()) == {g1}


def test_bit_group_validation_and_consistency() -> None:
    p0, p1 = Position3D(0, 0, 1), Position3D(1, 0, 1)
    generator = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    constraints = (
        ConditionalCubeConstraint(p0, ((0b0, 0), (0b0, 0))),
        ConditionalCubeConstraint(p1, ((0b0, 0), (0b0, 0))),
    )
    with pytest.raises(TQECError, match="without a closure constraint"):
        ConditionalCorrelationSurface(
            particular=generator,
            constraints=constraints[:1],
            bit_groups=(frozenset({p0, p1}),),
        )
    surface = ConditionalCorrelationSurface(
        particular=generator,
        constraints=constraints,
        bit_groups=(frozenset({p0, p1}),),
    )
    assert surface.resolve({p0: 1, p1: 1}) == generator
    with pytest.raises(TQECError, match="share one condition bit"):
        surface.resolve({p0: 0, p1: 1})


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


def test_observable_with_ports_pins_the_external_identity() -> None:
    g = BlockGraph("open with conditional")
    g.add_cube(Position3D(0, 0, 0), "PORT", "in")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_cube(Position3D(0, 0, 2), "PORT", "out")
    g.add_cube(Position3D(1, 0, 1), "ZXZ")
    g.add_cube(
        Position3D(1, 0, 2),
        "ZXZ_ZXX",
        condition=_surface(((0, 0, 1), (1, 0, 1), Basis.X)),
    )
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.add_pipe(Position3D(0, 0, 1), Position3D(0, 0, 2))
    g.add_pipe(Position3D(0, 0, 1), Position3D(1, 0, 1))
    g.add_pipe(Position3D(1, 0, 1), Position3D(1, 0, 2))
    g.validate()

    # The X flow from port to port avoids the conditional cube and resolves identically in
    # both branches, with the pinned external stabilizer.
    (x_flow,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.X))])
    assert x_flow.dependencies == frozenset()
    for value in (0, 1):
        resolved = x_flow.resolve(value)
        assert resolved.external_stabilizer_on_graph(g) == "XX"
        assert _in_gf2_span(
            resolved, g.resolve_conditional_kinds(value).find_correlation_surfaces()
        )

    # The Z flow spreads onto the merged ancilla and terminates on the conditional cube: it
    # only closes in the ZXZ branch. Compile-time completion succeeds (runtime-only
    # validation), and the unsolvable branch is reported by resolve().
    (z_flow,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    resolved = z_flow.resolve(0)
    assert resolved.external_stabilizer_on_graph(g) == "ZZ"
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
    # The merge observable routes its randomness to the magic port: it terminates with the
    # pinned X at the port and on the conditional cube, whose X-measurement branch is the
    # only solvable one. The closed Z initialization of the data column is avoided.
    g = _magic_merge_graph()
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 1), (1, 0, 1), Basis.X))])
    assert completed.dependencies == {Position3D(1, 0, 2)}
    resolved = completed.resolve(1)
    assert resolved.external_stabilizer_on_graph(g) == "X"
    assert Position3D(0, 0, 0) in resolved.positions
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(0)


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
    # single shared kernel coordinate. One cube carries a fold-relevant ``(coefficients=1,
    # target=1)`` branch row, but the two cubes require opposite values of that coordinate, so
    # the joint system is inconsistent and the surface must NOT collapse: both cubes remain
    # genuine dependencies. This exercises the joint-consistency check over a real (width-1)
    # kernel with several conditional cubes, guarding against over-eager collapsing.
    g = _chained_condition_graph(with_alternative_route=False)
    early, late = Position3D(1, 0, 2), Position3D(0, 0, 3)
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.X))])
    assert completed.dependencies == {early, late}
    assert len(completed.kernel) == 1
    # The cubes share one condition surface, hence one classical bit.
    assert completed.bit_groups == (frozenset({early, late}),)
    # Bit value 0 selects the conflicting branch rows and is unsolvable; value 1 is fine.
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(0)
    assert completed.resolve(1) is not None


def test_shared_condition_bits_are_grouped() -> None:
    g = _shared_bit_graph()
    p0, p1 = Position3D(0, 0, 1), Position3D(1, 0, 1)
    (completed,) = g.complete_observable_surfaces([_surface(((0, 0, 0), (0, 0, 1), Basis.Z))])
    assert completed.bit_groups == (frozenset({p0, p1}),)
    # The Z membrane spreads across the merge and terminates on both conditional cubes: it
    # closes when the shared bit selects the Z branches, and fails when it selects X.
    resolved = completed.resolve(0)
    assert resolved.bases_at(p0) == {Basis.Z}
    assert resolved.bases_at(p1) == {Basis.Z}
    with pytest.raises(TQECError, match="no valid resolution"):
        completed.resolve(1)
    with pytest.raises(TQECError, match="share one condition bit"):
        completed.resolve({p0: 0, p1: 1})
