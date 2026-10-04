import re
from collections import Counter

import pytest
import stim

from tqec import Basis, compile_block_graph
from tqec.compile.graph import TopologicalComputationGraph
from tqec.compile.tree.tree import CRUMBLE_COORDINATE_OFFSET, CRUMBLE_COORDINATE_SCALE
from tqec.gallery import memory
from tqec.post_processing.shift import transform_spatial_coordinates

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
    assert (CRUMBLE_COORDINATE_SCALE, CRUMBLE_COORDINATE_OFFSET) == (0.5, (0.0, 0.0))
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


def test_crumble_url_applies_the_coordinate_offset(graph: TopologicalComputationGraph) -> None:
    unscaled = graph.generate_crumble_url(1, coordinate_scale=1.0)
    moved = graph.generate_crumble_url(1, coordinate_scale=0.5, coordinate_offset=(1.0, -2.0))
    assert _qubit_coordinates(moved) == {
        i: (x / 2 + 1, y / 2 - 2) for i, (x, y) in _qubit_coordinates(unscaled).items()
    }


# Ground truth for the coordinate map: tqec memory patches against stim's generated rotated
# surface code and against Crumble's own surface code example.

Point = tuple[float, float]


def _layout(circuit: stim.Circuit) -> tuple[set[Point], dict[Point, tuple[str, frozenset[Point]]]]:
    """Return the data qubit positions and, per measure qubit position, its check basis and support.

    Data qubits are the qubits measured exactly once (at the end); measure qubits are measured
    every round. Stabilizers are read from the two-qubit gates of the first round: ``CZ`` or a
    ``CX`` targeting the measure qubit is a Z check, a ``CX`` controlled by it an X check.
    Qubits that only appear in ``QUBIT_COORDS`` are ignored.
    """
    coords = {q: (c[0], c[1]) for q, c in circuit.get_final_qubit_coordinates().items()}
    flat = circuit.flattened()
    measured = Counter(
        t.value
        for inst in flat
        if stim.gate_data(inst.name).produces_measurements
        for t in inst.targets_copy()
    )
    measure_qubits = {q for q, n in measured.items() if n > 1}
    data = {coords[q] for q, n in measured.items() if n == 1}
    checks: dict[int, tuple[str, set[Point]]] = {}
    for inst in flat:
        if stim.gate_data(inst.name).produces_measurements and any(
            t.value in measure_qubits for t in inst.targets_copy()
        ):
            break
        if inst.name not in ("CX", "CZ"):
            continue
        for control, target in inst.target_groups():
            c, t = control.value, target.value
            if inst.name == "CZ":
                m, d, basis = (c, t, "Z") if c in measure_qubits else (t, c, "Z")
            elif c in measure_qubits:
                m, d, basis = c, t, "X"
            else:
                m, d, basis = t, c, "Z"
            checks.setdefault(m, (basis, set()))[1].add(coords[d])
    return data, {coords[m]: (b, frozenset(ds)) for m, (b, ds) in checks.items()}


def _tqec_memory_circuit(k: int) -> stim.Circuit:
    # Detectors are irrelevant to the layout; ``manhattan_radius=0`` skips computing them.
    return compile_block_graph(memory(Basis.Z)).generate_stim_circuit(
        k, manhattan_radius=0, database_path=None
    )


@pytest.mark.parametrize("k", [1, 2])
def test_tqec_memory_layout_is_stim_rotated_memory_layout(k: int) -> None:
    distance = 2 * k + 1
    stim_memory = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=distance, rounds=3
    )
    tqec_data, tqec_checks = _layout(_tqec_memory_circuit(k))
    stim_data, stim_checks = _layout(stim_memory)
    assert len(tqec_data) == distance**2
    assert len(tqec_checks) == distance**2 - 1
    assert tqec_data == stim_data
    assert tqec_checks == stim_checks


# Qubit positions of the "Surface Code / Standard / Memory (V) / 5x5x3" example bundled with
# Crumble (glue/crumble/crumble.html in the stim repository), with the basis of each check.
_CRUMBLE_5X5_DATA = {(i + 0.5, j + 0.5) for i in range(5) for j in range(5)}
_CRUMBLE_5X5_CHECKS = {
    (0.0, 2.0): "X", (0.0, 4.0): "X", (1.0, 0.0): "Z", (1.0, 1.0): "X", (1.0, 2.0): "Z",
    (1.0, 3.0): "X", (1.0, 4.0): "Z", (2.0, 1.0): "Z", (2.0, 2.0): "X", (2.0, 3.0): "Z",
    (2.0, 4.0): "X", (2.0, 5.0): "Z", (3.0, 0.0): "Z", (3.0, 1.0): "X", (3.0, 2.0): "Z",
    (3.0, 3.0): "X", (3.0, 4.0): "Z", (4.0, 1.0): "Z", (4.0, 2.0): "X", (4.0, 3.0): "Z",
    (4.0, 4.0): "X", (4.0, 5.0): "Z", (5.0, 1.0): "X", (5.0, 3.0): "X",
}  # fmt: skip


def test_crumble_map_sends_tqec_memory_onto_crumble_example_positions() -> None:
    circuit = transform_spatial_coordinates(
        _tqec_memory_circuit(2), CRUMBLE_COORDINATE_SCALE, CRUMBLE_COORDINATE_OFFSET
    )
    data, checks = _layout(circuit)
    assert data == _CRUMBLE_5X5_DATA
    # The Crumble example is the patch with X and Z boundaries exchanged; positions agree exactly.
    swap = {"X": "Z", "Z": "X"}
    assert {m: swap[b] for m, (b, _) in checks.items()} == _CRUMBLE_5X5_CHECKS
