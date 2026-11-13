"""Detectors that the native detector path finds for the fixed-bulk Y half cube.

The Y half cube is built from a transition (SWITCH) round, ``REPEAT``ed padding (PAD) rounds and
a readout (FINAL) round. Two properties only show from ``k = 2``. The detectors of a ``REPEAT``
body are those of its first iteration, so the first PAD round must not be part of the
repetition. The diagonal domain wall of the SWITCH round spans the whole patch, so detectors
computed in a window smaller than the patch are not deterministic.
"""

import pytest
import stim
from tqecd.cover import find_commuting_cover_on_target_qubits
from tqecd.pauli import PauliString

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.computation.block_graph import BlockGraph
from tqec.gallery.memory import memory
from tqec.gallery.s_gate_teleportation import s_gate_teleportation
from tqec.utils.enums import PauliBasis
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def _y_memory() -> BlockGraph:
    """Y memory joined by a ``ZXO`` pipe: the half cube's top boundary is ``X``."""
    return memory(PauliBasis.Y)


def _y_memory_ztop() -> BlockGraph:
    """Y memory joined by an ``XZO`` pipe: the half cube's top boundary is ``Z``."""
    g = BlockGraph("Y memory, Z top")
    bottom = g.add_cube(Position3D(0, 0, 0), "Y")
    top = g.add_cube(Position3D(0, 0, 1), "Y")
    g.add_pipe(bottom, top, "XZO")
    return g


def _y_above_two_cubes() -> BlockGraph:
    """Two ``XZX`` cubes joined in space, each with a Y half cube on top."""
    g = BlockGraph("Y half cubes above two joined cubes")
    bottom = [g.add_cube(Position3D(x, 0, 0), "XZX") for x in range(2)]
    top = [g.add_cube(Position3D(x, 0, 1), "Y") for x in range(2)]
    g.add_pipe(bottom[0], bottom[1], "OZX")
    for b, t in zip(bottom, top):
        g.add_pipe(b, t, "XZO")
    return g


def _s_gate(basis: PauliBasis) -> BlockGraph:
    return s_gate_teleportation(basis)


def _tqecd_finds_minimal_commuting_covers() -> bool:
    """Whether the installed ``tqecd`` merges anticommuting flows with the fewest stabilizers.

    ``tqecd.cover.find_commuting_cover_on_target_qubits`` of tqecd 0.2.1 returns the first
    linear dependency it meets in source order, which is not always the smallest cover. On the
    example below it returns three stabilizers, ``[0, 1, 2]``, where ``Z0*Z1*Z2 * Z0*X1*Z2 = Y1``
    already commutes with ``Y0*Y1*Y2``. tqecd PR #74 (https://github.com/tqec/tqecd/pull/74)
    returns the minimal cover ``[2, 3]``. The surplus stabilizers of a non-minimal cover are
    flows that other detectors need, so with tqecd 0.2.1 some Y half cubes miss detectors in
    their SWITCH round and the gadget has distance 1 at every ``k``: the Y memory joined by an
    ``XZO`` pipe (``Z`` top boundary) is the simplest case. Which gadgets are hit depends on
    the order in which tqecd meets the flows; the Y memory joined by a ``ZXO`` pipe (``X`` top)
    keeps full distance only because its sources come in an order whose first dependency is
    minimal.
    """

    def pauli(text: str) -> PauliString:
        return PauliString.from_stim_pauli_string(stim.PauliString(text))

    cover = find_commuting_cover_on_target_qubits(
        pauli("YYY"), [pauli("_XZ"), pauli("Z__"), pauli("ZZZ"), pauli("ZXZ")]
    )
    return cover is not None and len(cover) == 2


NEEDS_MINIMAL_COVER = pytest.mark.xfail(
    condition=not _tqecd_finds_minimal_commuting_covers(),
    reason="tqecd 0.2.1 merges anticommuting flows with non-minimal covers (fixed in tqecd #74)",
    raises=AssertionError,
    strict=True,
)

GRAPHS = {
    "y_memory": _y_memory,
    "y_memory_ztop": _y_memory_ztop,
    "s_gate_x": lambda: _s_gate(PauliBasis.X),
    "s_gate_z": lambda: _s_gate(PauliBasis.Z),
    "y_above_two_cubes": _y_above_two_cubes,
}
# Gadgets whose full distance needs the minimal commuting cover of tqecd PR #74; see
# ``_tqecd_finds_minimal_commuting_covers``. All three join a Y half cube to an ``XZO`` pipe;
# ``s_gate_z`` does too but keeps full distance with tqecd 0.2.1.
LOSES_DISTANCE_WITHOUT_MINIMAL_COVER = {"y_memory_ztop", "s_gate_x", "y_above_two_cubes"}


def _graph_params(names: list[str]) -> list:
    return [
        pytest.param(
            name,
            marks=[NEEDS_MINIMAL_COVER] if name in LOSES_DISTANCE_WITHOUT_MINIMAL_COVER else [],
        )
        for name in names
    ]


def _assert_deterministic_with_full_distance(graph: BlockGraph, k: int) -> None:
    compiled = compile_block_graph(graph, FIXED_BULK_CONVENTION)
    circuit = compiled.generate_stim_circuit(k, database_path=None)
    # Raises a ValueError if any detector is non-deterministic.
    circuit.detector_error_model()
    noisy = NoiseModel.uniform_depolarizing(1e-3).noisy_circuit(circuit)
    error = noisy.shortest_graphlike_error(
        ignore_ungraphlike_errors=False, canonicalize_circuit_errors=True
    )
    assert len(error) == 2 * k + 1


@pytest.mark.timeout(0)
@pytest.mark.parametrize("name", _graph_params(["y_memory", "y_memory_ztop"]))
def test_y_memory_has_full_distance_in_both_orientations(name: str) -> None:
    _assert_deterministic_with_full_distance(GRAPHS[name](), k=1)


@pytest.mark.slow
@pytest.mark.timeout(0)
@pytest.mark.parametrize("k", [2])
@pytest.mark.parametrize("name", _graph_params(list(GRAPHS)))
def test_native_detectors_are_deterministic_with_full_distance(name: str, k: int) -> None:
    _assert_deterministic_with_full_distance(GRAPHS[name](), k)
