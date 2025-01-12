from tqec.compile.observables.abstract_observable import (
    AbstractObservable,
    compile_correlation_surface_to_abstract_observable,
)
from tqec.compile.specs.enums import JunctionArms
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, ZXCube
from tqec.computation.pipe import Pipe, PipeKind
from tqec.gallery.logical_cnot import logical_cnot_block_graph
from tqec.gallery.three_cnots import three_cnots_block_graph
from tqec.gallery.solo_node import solo_node_block_graph
from tqec.position import Position3D


def test_abstract_observable_for_single_cube() -> None:
    g = solo_node_block_graph("Z")
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(
            {Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))}
        ),
    )


def test_abstract_observable_for_single_vertical_pipe() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("ZXO"),
    )
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
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("OXZ"),
    )
    correlation_surfaces = g.find_correlation_surfaces()
    abstract_observable = compile_correlation_surface_to_abstract_observable(
        g, correlation_surfaces[0]
    )
    assert abstract_observable == AbstractObservable(
        top_readout_cubes=frozenset(g.nodes),
        top_readout_pipes=frozenset(g.edges),
    )


def test_abstract_observable_for_logical_cnot() -> None:
    g = logical_cnot_block_graph("Z")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 3
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
    assert observables[2] == AbstractObservable(
        top_readout_cubes=frozenset(
            [
                Cube(Position3D(0, 0, 3), ZXCube.from_str("ZXZ")),
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
    g = three_cnots_block_graph("Z")
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 7
    observables = [
        compile_correlation_surface_to_abstract_observable(g, correlation_surface)
        for correlation_surface in correlation_surfaces
    ]
    assert observables[0] == AbstractObservable(
        top_readout_cubes=frozenset(
            [
                Cube(Position3D(-1, 0, 0), ZXCube.from_str("ZXZ")),
                Cube(Position3D(0, -1, 0), ZXCube.from_str("XZZ")),
            ]
        ),
        top_readout_pipes=frozenset(
            [
                Pipe.from_cubes(
                    Cube(Position3D(-1, 0, 0), ZXCube.from_str("ZXZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(0, -1, 0), ZXCube.from_str("XZZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
            ]
        ),
        top_readout_spatial_junctions=frozenset(
            [
                (
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                    JunctionArms.LEFT | JunctionArms.DOWN,
                ),
            ]
        ),
    )
    assert observables[1] == AbstractObservable(
        top_readout_cubes=frozenset(
            [
                Cube(Position3D(-1, 0, 0), ZXCube.from_str("ZXZ")),
                Cube(Position3D(0, -1, 0), ZXCube.from_str("XZZ")),
                Cube(Position3D(2, 1, 0), ZXCube.from_str("ZXZ")),
            ]
        ),
        top_readout_pipes=frozenset(
            [
                Pipe.from_cubes(
                    Cube(Position3D(-1, 0, 0), ZXCube.from_str("ZXZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(0, -1, 0), ZXCube.from_str("XZZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(0, 1, 0), ZXCube.from_str("XXZ")),
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(0, 1, 0), ZXCube.from_str("XXZ")),
                    Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
                ),
                Pipe.from_cubes(
                    Cube(Position3D(2, 1, 0), ZXCube.from_str("ZXZ")),
                    Cube(Position3D(1, 1, 0), ZXCube.from_str("ZXZ")),
                ),
            ]
        ),
        top_readout_spatial_junctions=frozenset(
            [
                (
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                    JunctionArms.LEFT | JunctionArms.DOWN,
                ),
                (
                    Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
                    JunctionArms.RIGHT | JunctionArms.UP,
                ),
                (
                    Cube(Position3D(0, 1, 0), ZXCube.from_str("XXZ")),
                    JunctionArms.RIGHT | JunctionArms.DOWN,
                ),
            ]
        ),
        bottom_stabilizer_pipes=frozenset(
            [
                Pipe.from_cubes(
                    Cube(Position3D(1, 1, 1), ZXCube.from_str("ZXX")),
                    Cube(Position3D(1, 0, 1), ZXCube.from_str("ZXX")),
                ),
            ]
        ),
    )
    obs = observables[2]
    assert len(obs.top_readout_cubes) == 3
    assert len(obs.top_readout_pipes) == 4
    assert len(obs.bottom_stabilizer_pipes) == 1
    assert len(obs.top_readout_spatial_junctions) == 2

    obs = observables[3]
    assert len(obs.top_readout_cubes) == 2
    assert len(obs.top_readout_pipes) == 2
    assert len(obs.bottom_stabilizer_pipes) == 0
    assert len(obs.top_readout_spatial_junctions) == 1

    obs = observables[4]
    assert len(obs.top_readout_cubes) == 3
    assert len(obs.top_readout_pipes) == 4
    assert len(obs.bottom_stabilizer_pipes) == 1
    assert len(obs.top_readout_spatial_junctions) == 2

    obs = observables[5]
    assert len(obs.top_readout_cubes) == 2
    assert len(obs.top_readout_pipes) == 2
    assert len(obs.bottom_stabilizer_pipes) == 0
    assert len(obs.top_readout_spatial_junctions) == 1

    obs = observables[6]
    assert len(obs.top_readout_cubes) == 1
    assert len(obs.top_readout_pipes) == 4
    assert len(obs.bottom_stabilizer_pipes) == 1
    assert len(obs.top_readout_spatial_junctions) == 2
