import pytest

from tqec.computation.abstract_observable import AbstractObservable
from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import Cube, Port, YCube, ZXCube
from tqec.computation.pipe import PipeKind
from tqec.exceptions import TQECException
from tqec.gallery.solo_node import solo_node_block_graph
from tqec.position import Position3D


def test_abstract_observable_for_single_cube() -> None:
    g = solo_node_block_graph("Z")
    observables, correlation_surfaces = g.get_abstract_observables()
    assert len(observables) == len(correlation_surfaces) == 1
    assert observables[0] == AbstractObservable(
        top_lines=frozenset({Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ"))}),
        bottom_regions=frozenset(),
    )


def test_abstract_observable_open_ports() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 1), Port(), "open"),
        PipeKind.from_str("ZXO"),
    )
    with pytest.raises(
        TQECException,
        match="The block graph must have no open ports to support observables.",
    ):
        g.get_abstract_observables()


def test_abstract_observable_for_single_vertical_pipe() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("ZXO"),
    )
    observables, correlation_surfaces = g.get_abstract_observables()
    assert len(observables) == len(correlation_surfaces) == 1
    assert observables[0] == AbstractObservable(
        top_lines=frozenset({Cube(Position3D(0, 0, 1), ZXCube.from_str("ZXZ"))}),
        bottom_regions=frozenset(),
    )


def test_abstract_observable_for_single_horizontal_pipe() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("ZXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("ZXZ")),
        PipeKind.from_str("OXZ"),
    )
    observables, correlation_surfaces = g.get_abstract_observables()
    assert len(observables) == len(correlation_surfaces) == 1
    assert observables[0] == AbstractObservable(
        top_lines=frozenset([*g.nodes, *g.edges]),
        bottom_regions=frozenset(),
    )

    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), ZXCube.from_str("XXZ")),
        Cube(Position3D(1, 0, 0), ZXCube.from_str("XXZ")),
        PipeKind.from_str("OXZ"),
    )
    observables, correlation_surfaces = g.get_abstract_observables()
    assert len(observables) == len(correlation_surfaces) == 1
    assert observables[0] == AbstractObservable(
        top_lines=frozenset(),
        bottom_regions=frozenset(g.edges),
    )


def test_abstract_observable_for_y_cubes() -> None:
    g = BlockGraph()
    g.add_edge(
        Cube(Position3D(0, 0, 0), YCube()),
        Cube(Position3D(0, 0, 1), YCube()),
        PipeKind.from_str("XZO"),
    )
    observables, correlation_surfaces = g.get_abstract_observables()
    assert len(observables) == len(correlation_surfaces) == 1
    assert observables[0] == AbstractObservable(
        top_lines=frozenset({Cube(Position3D(0, 0, 1), YCube())}),
        bottom_regions=frozenset(),
    )
