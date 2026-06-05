import hashlib
import random

import networkx as nx
import pytest

from tqec.compile.compile import compile_block_graph
from tqec.computation.open_graph import fill_ports_for_minimal_simulation
from tqec.gallery.cnot import cnot
from tqec.gallery.move_rotation import move_rotation
from tqec.gallery.three_cnots import three_cnots

OPEN_PORT_EXAMPLES = {
    "cnot": cnot,
    "three_cnots": three_cnots,
    "move_rotation": move_rotation,
}

# "largest_first" is the production default; the rest probe ordering drift.
COLORING_STRATEGIES = [
    "largest_first",
    "smallest_last",
    "independent_set",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "saturation_largest_first",
    "random_sequential",
]


def _circuit_sha(filled) -> str:
    """SHA-256 of the filled graph's Stim circuit text.

    ``manhattan_radius=-1`` skips detectors (fast, no multiprocessing) while
    keeping the ``OBSERVABLE_INCLUDE`` ordering that the coloring drift perturbs.
    """
    circuit = compile_block_graph(
        filled.graph, observables=filled.observables
    ).generate_stim_circuit(1, manhattan_radius=-1, database_path=None)
    return hashlib.sha256(str(circuit).encode()).hexdigest()


def _fingerprint(filled_graphs) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Order-sensitive (sorted stabilizers, circuit sha) per clique."""
    return tuple((tuple(sorted(fg.stabilizers)), _circuit_sha(fg)) for fg in filled_graphs)


@pytest.mark.parametrize("search_small_area_observables", [True, False])
def test_fill_ports_for_minimal_simulation(search_small_area_observables: bool) -> None:
    graph = cnot()
    filled_graphs = fill_ports_for_minimal_simulation(graph, search_small_area_observables)
    assert len(filled_graphs) == 2
    g1, g2 = filled_graphs
    assert not g1.graph.is_open
    assert not g2.graph.is_open
    assert set(g2.stabilizers) == {"ZIZI", "ZZIZ"}
    assert set(g2.get_external_stabilizers()) == {"ZZII", "ZIZZ"}
    if search_small_area_observables:
        assert set(g1.stabilizers) == {"IXIX", "XIXX"}
        assert set(g1.get_external_stabilizers()) == {"IIXX", "XXIX"}
    else:
        assert set(g1.stabilizers) == {"XXXI", "XIXX"}
        assert set(g1.get_external_stabilizers()) == {"XXXI", "XXIX"}


@pytest.mark.parametrize("example", list(OPEN_PORT_EXAMPLES))
def test_fill_ports_deterministic_across_coloring_strategies(
    example: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Circuits must not depend on networkx's greedy_color strategy.

    Otherwise a networkx upgrade re-labels circuits, changes their sinter
    ``strong_id``, and produces duplicate gallery points.
    """
    graph_fn = OPEN_PORT_EXAMPLES[example]
    original_greedy_color = nx.algorithms.coloring.greedy_color

    def make_patched(strategy: str):
        def patched(g: nx.Graph, *args: object, **kwargs: object) -> dict[int, int]:
            if strategy == "random_sequential":
                random.seed(12345)
            return original_greedy_color(g, strategy=strategy)

        return patched

    fingerprints = {}
    for strategy in COLORING_STRATEGIES:
        monkeypatch.setattr(nx.algorithms.coloring, "greedy_color", make_patched(strategy))
        filled = fill_ports_for_minimal_simulation(graph_fn(), False)
        fingerprints[strategy] = _fingerprint(filled)

    distinct = set(fingerprints.values())
    assert len(distinct) == 1, (
        f"{example}: circuit text depends on coloring strategy:\n"
        + "\n".join(f"  {s}: {fp}" for s, fp in fingerprints.items())
    )


# Golden circuits. Regenerate (and review the diff) only on intended changes.
_GOLDEN_CIRCUITS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "cnot": [
        (
            ("XIXX", "XXXI"),
            "b5e8fe52188e80ef5fa6ab27afad578d81d56615589f679877130a371ec08e72",
        ),
        (
            ("ZIZI", "ZZIZ"),
            "156870d452fbec30cd4bafa6570b9af1a63c8973b708b351026fc883fd8f7082",
        ),
    ],
    "three_cnots": [
        (
            ("IZIZZI", "IZZIIZ", "ZIIZII"),
            "c0b42fea5e13cc2a700825547f61aa7534dd986d13d18602a572d0db38c9d073",
        ),
        (
            ("XIIXXI", "XXIXIX", "XXXXII"),
            "323b22495a084e0ef0075910b5ab0c60396ec4304108cc5d0796c1c5e0b9312a",
        ),
    ],
    "move_rotation": [
        (
            ("XX",),
            "47dc1b293171bd7900bd1fcb659147b3371effb46b937e81d8feb52fbe653b00",
        ),
        (
            ("ZZ",),
            "434ff554a149c0dee2f9313080eca26fb36e187f42aa7985630c7bf8b2933a41",
        ),
    ],
}


@pytest.mark.parametrize("example", list(_GOLDEN_CIRCUITS))
def test_fill_ports_circuit_golden_snapshot(example: str) -> None:
    """Pin canonical circuits; catches partition drift that sorting can't absorb."""
    filled = OPEN_PORT_EXAMPLES[example]().fill_ports_for_minimal_simulation()
    actual = sorted((tuple(sorted(fg.stabilizers)), _circuit_sha(fg)) for fg in filled)
    expected = sorted(_GOLDEN_CIRCUITS[example])
    assert actual == expected
