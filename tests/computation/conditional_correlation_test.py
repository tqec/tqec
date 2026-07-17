"""Tests for the correlation surface families of computations with conditional cubes."""

from itertools import combinations

import pytest

from tqec.computation.block_graph import BlockGraph
from tqec.computation.conditional import ConditionalCorrelationSurface
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
    """Two stacked conditional cubes: the later condition's completion crosses the earlier one.

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


def test_conditional_correlation_surface_resolve_anf() -> None:
    p1, p2 = Position3D(0, 0, 0), Position3D(1, 0, 0)
    base = _surface(((0, 0, 2), (0, 0, 3), Basis.Z))
    d1 = _surface(((0, 0, 2), (0, 0, 3), Basis.X))
    d2 = _surface(((1, 0, 2), (1, 0, 3), Basis.Z))
    d12 = _surface(((1, 0, 2), (1, 0, 3), Basis.X))
    family = ConditionalCorrelationSurface(
        base,
        (
            (frozenset({p1}), d1),
            (frozenset({p2}), d2),
            (frozenset({p1, p2}), d12),
        ),
    )
    assert family.dependencies == {p1, p2}
    assert family.resolve(0) == base
    assert family.resolve({p1: 0, p2: 0}) == base
    assert family.resolve({p1: 1, p2: 0}) == base ^ d1
    assert family.resolve({p1: 0, p2: 1}) == base ^ d2
    # the cross-term delta only applies when both bits are set
    assert family.resolve({p1: 1, p2: 1}) == base ^ d1 ^ d2 ^ d12
    assert family.resolve(1) == base ^ d1 ^ d2 ^ d12
    with pytest.raises(KeyError):
        family.resolve({p1: 1})


def test_conditional_correlation_surface_validation() -> None:
    base = _surface(((0, 0, 0), (0, 0, 1), Basis.Z))
    delta = _surface(((0, 0, 0), (0, 0, 1), Basis.X))
    with pytest.raises(TQECError, match="non-empty"):
        ConditionalCorrelationSurface(base, ((frozenset(), delta),))
    p = Position3D(0, 0, 0)
    with pytest.raises(TQECError, match="Duplicate delta"):
        ConditionalCorrelationSurface(base, ((frozenset({p}), delta), (frozenset({p}), delta)))
    with pytest.raises(TQECError, match="at least one edge"):
        ConditionalCorrelationSurface(base, ((frozenset({p}), CorrelationSurface(frozenset())),))


def test_conditional_correlation_surface_dict_round_trip() -> None:
    family = ConditionalCorrelationSurface(
        _surface(((0, 0, 0), (0, 0, 1), Basis.Z)),
        ((frozenset({Position3D(1, 0, 1)}), _surface(((0, 0, 0), (0, 0, 1), Basis.X))),),
        coins=frozenset({Position3D(0, 0, 0)}),
    )
    assert ConditionalCorrelationSurface.from_dict(family.to_dict()) == family


def test_find_conditional_delegates_on_static_graph() -> None:
    g = BlockGraph("memory")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXZ")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    families = g.find_conditional_correlation_surfaces()
    assert [family.base for family in families] == g.find_correlation_surfaces()
    assert all(not family.deltas and not family.coins for family in families)


def test_find_correlation_surfaces_raises_on_conditional_graph() -> None:
    g = _merge_then_conditional_graph()
    with pytest.raises(TQECError, match="find_conditional_correlation_surfaces"):
        g.find_correlation_surfaces()


def test_no_branch_invariant_observable_raises() -> None:
    # The Z observable of the memory column exists only in the ZXZ branch of the conditional
    # measurement: no observable class is valid under every branch assignment.
    g = _merge_then_conditional_graph()
    with pytest.raises(TQECError, match="valid under every resolution"):
        g.find_conditional_correlation_surfaces()
    with pytest.raises(TQECError, match="valid under every resolution"):
        g.find_conditional_correlation_surfaces(include_nondeterministic=True)


def test_route_around_observable_on_closed_graph() -> None:
    # The Z tube through the Z-spider hub avoids the conditional cube entirely and is a
    # deterministic observable in both branches. Recovering it requires the search to keep
    # the closed surfaces at the open conditional leaf.
    g = _route_around_graph()
    families = g.find_conditional_correlation_surfaces()
    assert len(families) == 1
    (family,) = families
    assert family.deltas == ()
    assert family.coins == frozenset()
    assert family.base == _surface(
        ((0, 0, 0), (1, 0, 0), Basis.Z),
        ((0, 0, 0), (0, 0, 1), Basis.Z),
        ((0, 0, 1), (0, 0, 2), Basis.Z),
    )
    # the resolution is a deterministic observable of both resolved static graphs
    for value in (0, 1):
        resolved_graph = g.resolve_conditional_kinds(value)
        assert _in_gf2_span(family.resolve(value), resolved_graph.find_correlation_surfaces())


def test_ports_with_conditional_cube() -> None:
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

    families = g.find_conditional_correlation_surfaces()
    # The X flow from port to port avoids the conditional cube; the Z flow spreads onto the
    # merged ancilla and only closes in the ZXZ branch, so it is excluded.
    assert len(families) == 1
    (family,) = families
    assert family.deltas == ()
    assert family.base.external_stabilizer_on_graph(g) == "XX"
    for value in (0, 1):
        resolved_graph = g.resolve_conditional_kinds(value)
        assert _in_gf2_span(family.resolve(value), resolved_graph.find_correlation_surfaces())


def test_coin_observable_requires_nondeterministic_flag() -> None:
    # Z-basis initialization followed by an X-basis measurement: the readout bit is a
    # uniformly random logical coin, evaluable on hardware but not deterministic.
    g = BlockGraph("coin readout")
    g.add_cube(Position3D(0, 0, 0), "ZXZ")
    g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    g.validate()

    with pytest.raises(TQECError, match="deterministic"):
        g.find_correlation_surfaces()
    # without the flag, the static contract applies (delegation on a conditional-free graph)
    with pytest.raises(TQECError, match="deterministic"):
        g.find_conditional_correlation_surfaces()
    families = g.find_conditional_correlation_surfaces(include_nondeterministic=True)
    assert len(families) == 1
    (family,) = families
    assert family.base == _surface(((0, 0, 0), (0, 0, 1), Basis.X))
    assert family.coins == frozenset({Position3D(0, 0, 0)})


def test_complete_condition_of_merge_outcome() -> None:
    # The merge-outcome condition completes into the X membrane running from the Z
    # initialization (an anticommuting termination contributing the merge coin), across the
    # merge, and dangling into the conditional cube's own interface.
    g = _merge_then_conditional_graph()
    completed = g.complete_condition(Position3D(1, 0, 2))
    assert completed.deltas == ()
    assert completed.coins == frozenset({Position3D(0, 0, 0)})
    assert completed.base == _surface(
        ((0, 0, 0), (0, 0, 1), Basis.X),
        ((0, 0, 1), (1, 0, 1), Basis.X),
        ((1, 0, 1), (1, 0, 2), Basis.X),
    )
    # every physical record of the condition is in the strict past of the conditional cube
    assert all(p.z < 2 or p == Position3D(1, 0, 2) for p in completed.base.positions)


def test_complete_condition_dangling_at_future_interface() -> None:
    # The declared condition of the route-around graph terminates matched on the sideways
    # leaf and dangles at the interface to the future part of the memory column.
    g = _route_around_graph(condition_basis=Basis.Z)
    completed = g.complete_condition(Position3D(0, 1, 1))
    assert completed.deltas == ()
    assert completed.coins == frozenset()
    assert completed.base == _surface(
        ((0, 0, 0), (1, 0, 0), Basis.Z),
        ((0, 0, 0), (0, 0, 1), Basis.Z),
    )


def test_complete_condition_anticommuting_measurement_leaf_raises() -> None:
    # An X strand pinned on the merge with the sideways leaf is unevaluable: the leaf's
    # exposed face is a Z-basis measurement, and X records do not exist there. Contrast with
    # `test_complete_condition_of_merge_outcome`, where the anticommuting termination lands on
    # an initialization face and is a valid coin.
    g = _route_around_graph(condition_basis=Basis.X)
    with pytest.raises(TQECError, match="cannot be completed"):
        g.complete_condition(Position3D(0, 1, 1))


def test_complete_condition_on_static_cube_raises() -> None:
    g = _merge_then_conditional_graph()
    with pytest.raises(TQECError, match="not a conditional cube"):
        g.complete_condition(Position3D(0, 0, 0))


def test_chained_condition_unsolvable_branch_raises() -> None:
    # The completion of the later condition is forced onto the earlier conditional cube with
    # an X termination, which is invalid when the earlier cube resolves to its Z branch.
    g = _chained_condition_graph(with_alternative_route=False)
    with pytest.raises(TQECError, match="resolve to"):
        g.complete_condition(Position3D(0, 0, 3))


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
