from typing import Literal

import pytest

from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    CubeWithArms,
    PipeWithArms,
    _check_correlation_surface_validity,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.compile.specs.enums import SpatialArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface, ZXEdge, ZXNode
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe
from tqec.gallery.cnot import cnot
from tqec.gallery.memory import memory
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.stability import stability
from tqec.gallery.three_cnots import three_cnots
from tqec.utils.enums import Basis, PauliBasis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Position3D


def test_abstract_observable_for_single_memory_cube() -> None:
    g = memory(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(
            {CubeWithArms(Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")))}
        ),
    )


def test_abstract_observable_for_single_stability_cube() -> None:
    g = stability(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        bottom_stabilizer_cubes=frozenset(
            {CubeWithArms(Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX")))}
        ),
    )


def test_abstract_observable_for_single_vertical_pipe() -> None:
    g = BlockGraph()
    p0, p1 = Position3D(0, 0, 0), Position3D(0, 0, 1)
    g.add_cube(p0, "ZXZ")
    g.add_cube(p1, "ZXZ")
    g.add_pipe(p0, p1)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(
            {CubeWithArms(Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ")))}
        ),
    )


def test_abstract_observable_for_single_horizontal_pipe() -> None:
    g = BlockGraph()
    p0, p1 = Position3D(0, 0, 0), Position3D(1, 0, 0)
    g.add_cube(p0, "ZXZ")
    g.add_cube(p1, "ZXZ")
    g.add_pipe(p0, p1)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(CubeWithArms(cube) for cube in g.cubes),
        top_readout_pipes=frozenset(PipeWithArms(pipe) for pipe in g.pipes),
    )


def test_abstract_observable_for_y_move_rotation() -> None:
    g = move_rotation(PauliBasis.Y)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert len(abstract_observable.top_readout_cubes) == 2
    assert len(abstract_observable.top_readout_pipes) == 2
    assert len(abstract_observable.bottom_stabilizer_pipes) == 2
    assert len(abstract_observable.bottom_stabilizer_cubes) == 0
    assert len(abstract_observable.temporal_hadamard_pipes) == 0
    assert len(abstract_observable.y_half_cubes) == 2


def test_abstract_observable_for_logical_cnot() -> None:
    g = cnot(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 2
    observables = [
        compile_correlation_surface_to_abstract_observable(g, correlation_surface)
        for correlation_surface in correlation_surfaces
    ]
    assert observables[0] == AbstractObservable(
        top_readout_cubes=frozenset(
            [CubeWithArms(Cube(Position3D(0, 0, 3), ZXCube.from_str("ZXZ")))]
        ),
    )
    assert observables[1] == AbstractObservable(
        top_readout_cubes=frozenset(
            [
                CubeWithArms(Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ"))),
                CubeWithArms(Cube(Position3D(1, 1, 3), ZXCube.from_str("ZXZ"))),
            ]
        ),
        top_readout_pipes=frozenset(
            [
                PipeWithArms(
                    Pipe.from_cubes(
                        Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ")),
                        Cube(Position3D(1, 1, 2), ZXCube.from_str("ZXZ")),
                    )
                )
            ]
        ),
        bottom_stabilizer_pipes=frozenset(
            [
                PipeWithArms(
                    Pipe.from_cubes(
                        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
                        Cube(Position3D(0, 1, 1), ZXCube.from_str("ZXX")),
                    )
                )
            ]
        ),
    )


def test_abstract_observable_for_three_cnots() -> None:
    g = three_cnots(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 3
    observables = [
        compile_correlation_surface_to_abstract_observable(g, correlation_surface)
        for correlation_surface in correlation_surfaces
    ]
    assert len(observables[0].top_readout_cubes) == 3
    assert len(observables[0].top_readout_pipes) == 2
    assert len(observables[0].bottom_stabilizer_pipes) == 0
    assert len(observables[0].bottom_stabilizer_cubes) == 0
    assert len(observables[0].temporal_hadamard_pipes) == 0

    assert len(observables[1].top_readout_cubes) == 3
    assert len(observables[1].top_readout_pipes) == 2
    assert len(observables[1].bottom_stabilizer_pipes) == 0
    assert len(observables[1].bottom_stabilizer_cubes) == 0
    assert len(observables[1].temporal_hadamard_pipes) == 0

    assert len(observables[2].top_readout_cubes) == 3
    assert len(observables[2].top_readout_pipes) == 4
    assert len(observables[2].bottom_stabilizer_pipes) == 1
    assert len(observables[2].bottom_stabilizer_cubes) == 0
    assert len(observables[2].temporal_hadamard_pipes) == 0


def test_abstract_observable_for_temporal_hadamard() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "XZZ")
    n2 = g.add_cube(Position3D(0, 0, 1), "ZXX")
    g.add_pipe(n1, n2)
    surfaces = g.find_correlation_surfaces()
    assert len(surfaces) == 1
    observable = compile_correlation_surface_to_abstract_observable(
        g, surfaces[0], include_temporal_hadamard_pipes=True
    )
    assert len(observable.top_readout_cubes) == 1
    assert len(observable.temporal_hadamard_pipes) == 1


def test_x_correlation_surface_on_x_node_four_arms() -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), "ZZX")
    n2 = g.add_cube(Position3D(1, 0, 0), "XZX")
    n3 = g.add_cube(Position3D(-1, 0, 0), "XZX")
    n4 = g.add_cube(Position3D(0, 1, 0), "ZXX")
    n5 = g.add_cube(Position3D(0, -1, 0), "ZXX")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    g.add_pipe(n1, n4)
    g.add_pipe(n1, n5)
    zx = g.to_zx_graph()
    center = zx.p2v[Position3D(0, 0, 0)]
    corrlation_surface = CorrelationSurface(
        frozenset(
            {
                ZXEdge(ZXNode(center, Basis.X), (ZXNode(n, Basis.X)))
                for n in zx.g.vertex_set()
                if n != center
            }
        )
    )
    obs = compile_correlation_surface_to_abstract_observable(g, corrlation_surface)
    assert len(obs.top_readout_cubes) == 6
    assert (
        CubeWithArms(
            Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX")), SpatialArms.LEFT | SpatialArms.DOWN
        )
        in obs.top_readout_cubes
    )
    assert (
        CubeWithArms(
            Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX")), SpatialArms.UP | SpatialArms.RIGHT
        )
        in obs.top_readout_cubes
    )


def _make_correlation_surface(edges: list[tuple[int, Literal["Z", "X"]]]) -> CorrelationSurface:
    return CorrelationSurface(
        frozenset(
            {
                ZXEdge(ZXNode(u[0], Basis(u[1])), ZXNode(v[0], Basis(v[1])))
                for u, v in zip(edges[::2], edges[1::2])
            }
        )
    )


@pytest.mark.parametrize("cross_center", ("ZZX", "XXZ"))
def test_correlation_surface_validity_raise(cross_center: str) -> None:
    g = BlockGraph()
    n1 = g.add_cube(Position3D(0, 0, 0), cross_center)
    n2 = g.add_cube(Position3D(1, 0, 0), "P", "P1")
    n3 = g.add_cube(Position3D(-1, 0, 0), "P", "P2")
    n4 = g.add_cube(Position3D(0, 1, 0), "P", "P3")
    n5 = g.add_cube(Position3D(0, -1, 0), "P", "P4")
    g.add_pipe(n1, n2)
    g.add_pipe(n1, n3)
    g.add_pipe(n1, n4)
    g.add_pipe(n1, n5)
    cross = g.to_zx_graph().g
    nb = "X" if cross_center == "ZZX" else "Z"
    ab = "Z" if cross_center == "ZZX" else "X"
    with pytest.raises(TQECError):
        _check_correlation_surface_validity(_make_correlation_surface([(5, nb), (5, nb)]), cross)
    with pytest.raises(TQECError):
        _check_correlation_surface_validity(_make_correlation_surface([(0, nb), (2, nb)]), cross)
    with pytest.raises(TQECError):
        _check_correlation_surface_validity(
            _make_correlation_surface([(0, nb), (2, nb), (2, nb), (3, nb), (2, nb), (4, nb)]),
            cross,
        )
    with pytest.raises(TQECError):
        _check_correlation_surface_validity(
            _make_correlation_surface([(0, ab), (2, ab)]),
            cross,
        )

    y_g = BlockGraph()
    ny = y_g.add_cube(Position3D(0, 0, 0), "Y")
    np = y_g.add_cube(Position3D(0, 0, 1), "P", "Port")
    y_g.add_pipe(ny, np, "ZXO")
    with pytest.raises(TQECError):
        _check_correlation_surface_validity(
            _make_correlation_surface([(0, "Z"), (1, "Z")]), y_g.to_zx_graph().g
        )
