"""Tests for the branch-resolvable correlation surfaces of conditional computations."""

from itertools import combinations

import pytest

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


def _merge_then_conditional_graph() -> BlockGraph:
    """Build a Z memory column merged with an ancilla measured in a conditional basis."""
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

    Without the alternative route through ``(1, 0, 0)``, the only completion of the later
    condition terminates with X on the earlier conditional cube, which is invalid when that
    cube resolves to its Z-measurement branch.
    """
    g = BlockGraph("chained conditions")
    condition = _surface(((0, 0, 1), (1, 0, 1), Basis.X))
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
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
        g.add_cube(Position3D(1, 0, 0), "ZXZ")
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
        generators=(g0, g1),
        particular=0b01,
        kernel=(0b11,),
        # branch 0 is satisfied by the particular combination; branch 1 needs the kernel
        # element XORed in.
        constraints=(ConditionalCubeConstraint(p, ((0b0, 0), (0b1, 1))),),
        coin_rows=((Position3D(0, 0, 0), 0b1, 0),),
    )
    assert surface.dependencies == {p}
    assert surface.resolve(0) == g0
    assert surface.resolve({p: 1}) == g1
    assert surface.coins(0) == frozenset()
    assert surface.coins(1) == frozenset({Position3D(0, 0, 0)})
    with pytest.raises(KeyError):
        surface.resolve({})


def test_resolve_raises_on_inconsistent_branch() -> None:
    p = Position3D(0, 0, 1)
    surface = ConditionalCorrelationSurface(
        generators=(_surface(((0, 0, 0), (0, 0, 1), Basis.Z)),),
        particular=0b1,
        constraints=(ConditionalCubeConstraint(p, ((0b0, 0), (0b0, 1))),),
    )
    assert surface.resolve(0) == surface.generators[0]
    with pytest.raises(TQECError, match="no valid resolution"):
        surface.resolve(1)


def test_bit_group_validation_and_consistency() -> None:
    p0, p1 = Position3D(0, 0, 1), Position3D(1, 0, 1)
    generator = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    constraints = (
        ConditionalCubeConstraint(p0, ((0b0, 0), (0b0, 0))),
        ConditionalCubeConstraint(p1, ((0b0, 0), (0b0, 0))),
    )
    with pytest.raises(TQECError, match="without a closure constraint"):
        ConditionalCorrelationSurface(
            generators=(generator,),
            particular=0b1,
            constraints=constraints[:1],
            bit_groups=(frozenset({p0, p1}),),
        )
    surface = ConditionalCorrelationSurface(
        generators=(generator,),
        particular=0b1,
        constraints=constraints,
        bit_groups=(frozenset({p0, p1}),),
    )
    assert surface.resolve({p0: 1, p1: 1}) == generator
    with pytest.raises(TQECError, match="share one condition bit"):
        surface.resolve({p0: 0, p1: 1})


def test_dict_round_trip() -> None:
    completed = _merge_then_conditional_graph().complete_condition(Position3D(1, 0, 2))
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
    expected = _surface(
        ((0, 0, 0), (1, 0, 0), Basis.Z),
        ((0, 0, 0), (0, 0, 1), Basis.Z),
        ((0, 0, 1), (0, 0, 2), Basis.Z),
    )
    for value in (0, 1):
        assert completed.resolve(value) == expected
        assert completed.coins(value) == frozenset()
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


def test_coin_observable_requires_nondeterministic_flag() -> None:
    # Z-basis initialization followed by an X-basis measurement: the readout bit is a
    # uniformly random logical coin, evaluable on hardware but not deterministic.
    g = BlockGraph("coin readout")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.validate()
    spec = _surface(((0, 0, 0), (0, 0, 1), Basis.X))

    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_observable_surfaces([spec])
    (completed,) = g.complete_observable_surfaces([spec], include_nondeterministic=True)
    assert completed.resolve(0) == spec
    assert completed.coins(0) == frozenset({Position3D(0, 0, 0)})


def test_complete_condition_of_merge_outcome() -> None:
    # The merge-outcome condition completes into the X membrane running from the Z
    # initialization (an anticommuting termination contributing the merge coin), across the
    # merge, and dangling into the conditional cube's own interface.
    g = _merge_then_conditional_graph()
    completed = g.complete_condition(Position3D(1, 0, 2))
    assert completed.constraints == ()
    assert completed.resolve(0) == _surface(
        ((0, 0, 0), (0, 0, 1), Basis.X),
        ((0, 0, 1), (1, 0, 1), Basis.X),
        ((1, 0, 1), (1, 0, 2), Basis.X),
    )
    assert completed.coins(0) == frozenset({Position3D(0, 0, 0)})
    # every physical record of the condition is in the strict past of the conditional cube
    assert all(p.z < 2 or p == Position3D(1, 0, 2) for p in completed.resolve(0).positions)


def test_complete_condition_dangling_at_future_interface() -> None:
    # The declared condition of the route-around graph terminates matched on the sideways
    # leaf and dangles at the interface to the future part of the memory column.
    g = _route_around_graph(condition_basis=Basis.Z)
    completed = g.complete_condition(Position3D(0, 1, 1))
    assert completed.resolve(0) == _surface(
        ((0, 0, 0), (1, 0, 0), Basis.Z),
        ((0, 0, 0), (0, 0, 1), Basis.Z),
    )
    assert completed.coins(0) == frozenset()


def test_complete_condition_anticommuting_measurement_leaf_raises() -> None:
    # An X strand pinned on the merge with the sideways leaf is unevaluable: the leaf's
    # exposed face is a Z-basis measurement, and X records do not exist there. Contrast with
    # `test_complete_condition_of_merge_outcome`, where the anticommuting termination lands
    # on an initialization face and is a valid coin.
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
