import re

import pytest

from tqec import Basis, compile_block_graph
from tqec.compile.graph import TopologicalComputationGraph
from tqec.gallery import memory

_QUBIT_COORDS_RE = re.compile(r"Q\(([^,)]*),([^)]*)\)(\d+)")
_DETECTOR_RE = re.compile(r"DT\(([^)]*)\)")


@pytest.fixture(name="graph", scope="module")
def graph_fixture() -> TopologicalComputationGraph:
    return compile_block_graph(memory(Basis.Z))


def _qubit_coordinates(url: str) -> dict[int, tuple[float, float]]:
    return {int(i): (float(x), float(y)) for x, y, i in _QUBIT_COORDS_RE.findall(url)}


def _detector_coordinates(url: str) -> list[tuple[float, ...]]:
    return [tuple(float(v) for v in args.split(",")) for args in _DETECTOR_RE.findall(url)]


def _polygons(url: str) -> list[str]:
    return re.findall(r"POLYGON\([^)]*\)[0-9_]+", url)


@pytest.mark.parametrize("add_polygons", [True, False])
def test_crumble_url_coordinates_are_halved_by_default(
    graph: TopologicalComputationGraph, add_polygons: bool
) -> None:
    unscaled = graph.generate_crumble_url(1, add_polygons=add_polygons, coordinate_scale=1.0)
    default = graph.generate_crumble_url(1, add_polygons=add_polygons)
    half = graph.generate_crumble_url(1, add_polygons=add_polygons, coordinate_scale=0.5)
    assert default == half

    unscaled_coords = _qubit_coordinates(unscaled)
    half_coords = _qubit_coordinates(half)
    assert unscaled_coords
    assert half_coords == {i: (x / 2, y / 2) for i, (x, y) in unscaled_coords.items()}

    unscaled_detectors = _detector_coordinates(unscaled)
    assert unscaled_detectors
    assert _detector_coordinates(half) == [
        (x / 2, y / 2, *rest) for x, y, *rest in unscaled_detectors
    ]


def test_crumble_url_polygons_are_unchanged_by_the_scale(
    graph: TopologicalComputationGraph,
) -> None:
    unscaled = graph.generate_crumble_url(1, add_polygons=True, coordinate_scale=1.0)
    half = graph.generate_crumble_url(1, add_polygons=True, coordinate_scale=0.5)
    assert _polygons(unscaled)
    assert _polygons(unscaled) == _polygons(half)


def test_crumble_url_scale_does_not_change_the_stim_circuit() -> None:
    graph = compile_block_graph(memory(Basis.Z))
    before = graph.generate_stim_circuit(1, database_path=None)
    graph.generate_crumble_url(1, add_polygons=True, coordinate_scale=0.5)
    graph.generate_crumble_url(1, add_polygons=False, coordinate_scale=0.5)
    after = graph.generate_stim_circuit(1, database_path=None)
    fresh = compile_block_graph(memory(Basis.Z)).generate_stim_circuit(1, database_path=None)
    assert before == after == fresh
    # Coordinates of the generated circuit stay on the original lattice (not halved).
    unscaled_coords = _qubit_coordinates(
        graph.generate_crumble_url(1, add_polygons=False, coordinate_scale=1.0)
    )
    circuit_coords = fresh.get_final_qubit_coordinates()
    assert {tuple(v) for v in circuit_coords.values()} == set(unscaled_coords.values())
