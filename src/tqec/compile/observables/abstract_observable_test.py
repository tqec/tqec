from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe
from tqec.gallery.cnot import cnot
from tqec.gallery.three_cnots import three_cnots
from tqec.gallery.memory import memory
from tqec.gallery.stability import stability
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D


def test_abstract_observable_for_single_memory_cube() -> None:
    g = memory(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(
            {Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))}
        ),
    )


def test_abstract_observable_for_single_stability_cube() -> None:
    g = stability(Basis.Z)
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        bottom_stabilizer_spatial_cubes=frozenset(
            {Cube(Position3D(0, 0, 0), ZXCube.from_str("ZZX"))}
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
            {Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ"))}
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
        top_readout_cubes=frozenset(g.cubes),
        top_readout_pipes=frozenset(g.pipes),
    )


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
            [Cube(Position3D(0, 0, 3), ZXCube.from_str("ZXZ"))]
        ),
    )
    assert observables[1] == AbstractObservable(
        top_readout_cubes=frozenset(
            [
                Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ")),
                Cube(Position3D(1, 1, 3), ZXCube.from_str("ZXZ")),
            ]
        ),
        top_readout_pipes=frozenset(
            [
                Pipe.from_cubes(
                    Cube(Position3D(0, 1, 2), ZXCube.from_str("ZXZ")),
                    Cube(Position3D(1, 1, 2), ZXCube.from_str("ZXZ")),
                )
            ]
        ),
        bottom_stabilizer_pipes=frozenset(
            [
                Pipe.from_cubes(
                    Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXX")),
                    Cube(Position3D(0, 1, 1), ZXCube.from_str("ZXX")),
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
    assert len(observables[0].top_readout_cubes) == 2
    assert len(observables[0].top_readout_pipes) == 2
    assert len(observables[0].top_readout_spatial_cubes) == 1
    assert len(observables[0].bottom_stabilizer_pipes) == 0
    assert len(observables[0].bottom_stabilizer_spatial_cubes) == 0

    assert len(observables[1].top_readout_cubes) == 2
    assert len(observables[1].top_readout_pipes) == 2
    assert len(observables[1].top_readout_spatial_cubes) == 1
    assert len(observables[1].bottom_stabilizer_pipes) == 0
    assert len(observables[1].bottom_stabilizer_spatial_cubes) == 0

    assert len(observables[2].top_readout_cubes) == 1
    assert len(observables[2].top_readout_pipes) == 4
    assert len(observables[2].top_readout_spatial_cubes) == 2
    assert len(observables[2].bottom_stabilizer_pipes) == 1
    assert len(observables[2].bottom_stabilizer_spatial_cubes) == 0
