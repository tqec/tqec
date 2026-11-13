"""Templates and plaquettes for the fixed-bulk Y half cube.

The Y-basis initialization/measurement half cube deforms a surface-code patch into a degenerate
patch through a single bespoke *transition* (SWITCH) round carrying a diagonal domain wall
(``CY`` twist couplings, an ``S`` fold, and a single-corner ``MY``), followed by ordinary
stabiliser rounds on the degenerate patch (PAD) and a data readout (FINAL).

The whole circuit is expressed with the standard Templates/Plaquettes framework: each round is a
``PlaquetteLayer`` over a bespoke :class:`~tqec.templates.base.RectangularTemplate`, so the half
cube composes as a normal :class:`~tqec.compile.blocks.block.Block` and its detectors are
recovered downstream by ``tqecd``. Restricted to the ``fixed_bulk`` convention (top-left tile
basis always ``Z``, so the ``XCY``/``SQRT_X`` branches of the general construction never fire).

The geometry/schedule is a direct port of Craig Gidney's inplace-y-basis construction
(https://github.com/Strilanc/inplace-y-basis-2023).
The construction follows Gidney, "Inplace Access to the Surface Code Y Basis", Quantum 8, 1310
(2024), https://doi.org/10.22331/q-2024-04-08-1310.

Note on ``d = 7``: with the padding of the paper (``d // 2`` padding rounds on each side),
Gidney's published circuit at ``d = 7`` has a logical error made of 6 faults, so its circuit
distance is at most 6, not 7. Gidney's source mentions this
(https://doi.org/10.5281/zenodo.7487893). A ``tqec`` circuit matched to Gidney's layout and noise
has the same 6-fault logical error in both orientations (X top and Z top).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Literal

import numpy
import numpy.typing as npt
import stim

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.base import BaseComposedLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.specs.base import YHalfCubeSpec
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import BorderIndices, RectangularTemplate
from tqec.templates.enums import TemplateBorder
from tqec.utils.enums import Basis as TQECBasis
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.scale import LinearFunction, PlaquetteScalable2D

Basis = Literal["X", "Z"]
# The half cube emits three round kinds: the transition (SWITCH), the degenerate-patch
# padding rounds (PAD), and the diagonal data readout (FINAL). There is
# deliberately no HOLD/idle round --
# SWITCH is the connected temporal border and sits directly on
# the neighbour's held state
# (see ``get_y_half_cube_block``); any state-preserving idling is left to be
# handled macroscopically over the block graph.
RoundKind = Literal["switch", "pad", "final"]

# Interaction directions (matching the plaquette orderings used across TQEC).
DIRS: list[complex] = [(0.5 + 0.5j) * 1j**d for d in range(4)]
DR, DL, UL, UR = DIRS
ORDER_H = [UL, UR, DL, DR]
ORDER_V = [UL, DL, UR, DR]

# Map an interaction direction to the local ``SquarePlaquetteQubits`` corner index
# (data corners UL,UR,DL,DR -> 0,1,2,3; syndrome -> 4).
_DIR_TO_CORNER = {UL: 0, UR: 1, DL: 2, DR: 3}
_SYNDROME = 4

# Data-qubit operations shared between neighbouring plaquettes are deduplicated on merge.
_MERGEABLE = frozenset({"H", "MX", "MY", "MZ", "M", "RX", "RY", "RZ", "R", "S", "S_DAG"})


def _flipped(b: Basis) -> Basis:
    return "Z" if b == "X" else "X"


# --------------------------------------------------------------------------------------------
# Geometry (gen-free): tiles, patches
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Tile:
    basis: Basis
    measure_qubit: complex
    data_qubits: tuple[complex | None, ...]

    @property
    def used_set(self) -> set[complex]:
        return {self.measure_qubit} | {q for q in self.data_qubits if q is not None}


@dataclass(frozen=True)
class _Patch:
    tiles: tuple[_Tile, ...]

    @property
    def data_set(self) -> set[complex]:
        return {q for t in self.tiles for q in t.data_qubits if q is not None}

    @property
    def used_set(self) -> set[complex]:
        s: set[complex] = set()
        for t in self.tiles:
            s |= t.used_set
        return s


def _checkerboard_basis(q: complex, top_left_tile_basis: Basis) -> Basis:
    if int(q.real + q.imag) & 1 == 0:
        return _flipped(top_left_tile_basis)
    return top_left_tile_basis


def _surface_code_patch(possible_data_qubits, basis, is_boundary_x, is_boundary_z, order_func):
    possible_data_qubits = set(possible_data_qubits)
    possible_measure_qubits = {q + d for q in possible_data_qubits for d in DIRS}
    measure_qubits = {
        m
        for m in possible_measure_qubits
        if sum(m + d in possible_data_qubits for d in DIRS) > 1
        if is_boundary_x(m) <= (basis(m) == "X")
        if is_boundary_z(m) <= (basis(m) == "Z")
    }
    data_qubits = {
        q for q in possible_data_qubits if sum(q + d in measure_qubits for d in DIRS) > 1
    }
    tiles = tuple(
        _Tile(
            basis=basis(m),
            data_qubits=tuple(
                m + d if d is not None and m + d in data_qubits else None for d in order_func(m)
            ),
            measure_qubit=m,
        )
        for m in measure_qubits
    )
    return _Patch(tiles)


def _rectangular_patch(width, height, top_basis, bot_basis, left_basis, right_basis, order_func):
    def is_boundary(m: complex, *, b: Basis) -> bool:
        if top_basis == b and m.imag == -0.5:
            return True
        if left_basis == b and m.real == -0.5:
            return True
        if bot_basis == b and m.imag == height - 0.5:
            return True
        if right_basis == b and m.real == width - 0.5:
            return True
        return False

    return _surface_code_patch(
        possible_data_qubits=[x + 1j * y for x in range(width) for y in range(height)],
        basis=lambda q: _checkerboard_basis(q, "Z"),  # fixed_bulk: top-left tile basis is Z
        is_boundary_x=lambda m: is_boundary(m, b="X"),
        is_boundary_z=lambda m: is_boundary(m, b="Z"),
        order_func=order_func,
    )


def _order_func(top_boundary_basis: Basis):
    def order(m: complex):
        if (_checkerboard_basis(m, "Z") == "X") ^ (top_boundary_basis == "Z"):
            return ORDER_H
        return ORDER_V

    return order


def _qubit_patch(distance: int, top: Basis) -> _Patch:
    return _rectangular_patch(
        distance, distance, top, top, _flipped(top), _flipped(top), _order_func(top)
    )


def _degenerate_patch(distance: int, top: Basis) -> _Patch:
    if top == "X":
        top_b = right_b = "Z"
        left_b = bot_b = "X"
    else:
        top_b = right_b = "X"
        left_b = bot_b = "Z"
    return _rectangular_patch(distance, distance, top_b, bot_b, left_b, right_b, _order_func(top))


def _split_ul_md_dr(ps: Iterable[complex], distance: int):
    ul: set[complex] = set()
    md: set[complex] = set()
    dr: set[complex] = set()
    for m in ps:
        if m.real + m.imag < distance - 2:
            ul.add(m)
        elif m.real + m.imag >= distance:
            dr.add(m)
        else:
            md.add(m)
    return ul, md, dr


def _toward(qs, delta, sign, used):
    result = set()
    for q in qs:
        if q + delta in used:
            result.add((q, q + delta) if sign == 1 else (q + delta, q))
    return result


# A "round" is a list of moments; a moment is a list of ``(gate, targets)`` where ``targets``
# is a list of complex (1-qubit) or ordered (control, target) complex pairs (2-qubit).
Moment = list
Round = list


def _final_measure_data_basis(data_qubits, top: Basis) -> dict[complex, Basis]:
    if top == "Z":
        return {q: ("Z" if q.real < q.imag else "X") for q in data_qubits}
    return {q: ("X" if q.real <= q.imag else "Z") for q in data_qubits}


def _standard_round(patch: _Patch, measure_data_basis: dict[complex, Basis] | None = None) -> Round:
    measure_data_basis = measure_data_basis or {}
    xs = [t for t in patch.tiles if t.basis == "X"]
    zs = [t for t in patch.tiles if t.basis == "Z"]
    moments: Round = [
        [
            ("RX", [t.measure_qubit for t in xs]),
            ("R", [t.measure_qubit for t in zs]),
        ]
    ]
    for k in range(4):
        pairs = []
        for t in patch.tiles:
            dq = t.data_qubits[k]
            if dq is None:
                continue
            pairs.append((dq, t.measure_qubit) if t.basis == "Z" else (t.measure_qubit, dq))
        moments.append([("CX", pairs)])
    meas: Moment = [("MX", [t.measure_qubit for t in xs])]
    for basis, gate in (("X", "MX"), ("Z", "M")):
        qs = [q for q, b in measure_data_basis.items() if b == basis]
        if qs:
            meas.append((gate, qs))
    meas.append(("M", [t.measure_qubit for t in zs]))
    moments.append(meas)
    return moments


def _transition_round(distance: int, top: Basis) -> Round:
    start = _qubit_patch(distance, top)
    end = _degenerate_patch(distance, top)
    used = start.used_set | end.used_set

    def _m_basis(m: complex) -> Basis | None:
        if m.real % 1 == 0:
            return None
        return _checkerboard_basis(m, "Z")

    xs = {q for q in used if _m_basis(q) == "X"}
    zs = {q for q in used if _m_basis(q) == "Z"}
    top_row = {q for q in used if q.imag == -0.5}
    left_col = {q for q in used if q.real == -0.5}
    xs_ul, xs_md, xs_dr = _split_ul_md_dr(xs, distance)
    zs_ul, zs_md, zs_dr = _split_ul_md_dr(zs, distance)

    if top == "X":
        nx, nz = ORDER_H, ORDER_V
        old_x, new_x = top_row, left_col
        old_z, new_z = left_col, top_row
    else:
        nx, nz = ORDER_V, ORDER_H
        old_x, new_x = left_col, top_row
        old_z, new_z = top_row, left_col

    r: Round = []
    r.append([("RX", list((xs - new_x) | old_x)), ("R", list((zs - new_z) | old_z))])
    r.append(
        [
            ("CX", _toward(xs - new_x, nx[-1], +1, used)),
            ("CX", _toward(zs - new_z, nz[-1], -1, used)),
        ]
    )
    r.append(
        [
            ("CX", _toward(xs - new_x, nx[-2], +1, used)),
            ("CX", _toward(zs - new_z, nz[-2], -1, used)),
        ]
    )
    r.append(
        [
            ("CX", _toward(xs_ul, nx[-3], -1, used)),
            ("CX", _toward(zs_ul | zs_md, nz[-3], +1, used)),
            ("CY", _toward(xs_md, nx[-3], +1, used)),
            ("CX", _toward(xs_dr, nx[-3], +1, used)),
            ("CX", _toward(zs_dr, nz[-3], -1, used)),
        ]
    )
    r.append(
        [
            ("CX", _toward(xs_ul, nx[-1], -1, used)),
            ("CX", _toward(zs_ul, nx[-1], +1, used)),
            ("CX", _toward(xs_dr, nx[-4], +1, used)),
            ("CX", _toward(zs_dr, nz[-4], -1, used)),
        ]
    )
    r.append([("CY", _toward(zs_md - old_z, nz[-1], -1, used))])
    r.append(
        [
            ("H", [q for q in used if q.real + q.imag < distance - 1]),
            (
                "S",
                [q for q in used if q.real + q.imag == distance - 1 and q.real % 1 == 0.5],
            ),
        ]
    )
    my_target = complex(0, distance - 1) if top == "X" else complex(distance - 1, 0)
    r.append(
        [
            ("MX", list((xs - old_x) | new_x)),
            ("MY", [my_target]),
            ("M", list((zs - old_z) | new_z)),
        ]
    )
    return r


_REV_GATE = {
    "R": "M",
    "M": "R",
    "RX": "MX",
    "MX": "RX",
    "RY": "MY",
    "MY": "RY",
    "H": "H",
    "S": "S_DAG",
    "S_DAG": "S",
    "CX": "CX",
    "CY": "CY",
    "CZ": "CZ",
}


def _time_reverse(rnd: Round) -> Round:
    return [[(_REV_GATE[g], targets) for g, targets in moment] for moment in reversed(rnd)]


# --------------------------------------------------------------------------------------------
# Round -> per-plaquette local ops (ancilla-centric decomposition)
# --------------------------------------------------------------------------------------------
def _is_syndrome(q: complex) -> bool:
    return q.real % 1 != 0


def _decompose_round(
    rnd: Round,
) -> dict[complex, dict[int, list[tuple[str, tuple[int, ...]]]]]:
    """Decompose a round into per-syndrome local ops keyed by timestep.

    Returns ``{syndrome: {timestep: [(gate, local_indices), ...]}}``. Single-qubit ops on data
    qubits (fold ``H`` / corner ``MY`` / data reset+measure) are attributed to every adjacent
    syndrome as a shared (mergeable) corner op.
    """
    # Syndromes are identified structurally (measure qubits sit on the half-integer sublattice).
    # This is robust to the init (time-reversed) direction, where the first moment also resets
    # data qubits (the reverse of the data readout).
    syndromes: set[complex] = set()
    for moment in rnd:
        for _, targets in moment:
            for t in targets:
                for q in t if isinstance(t, tuple) else (t,):
                    if _is_syndrome(q):
                        syndromes.add(q)

    per_syn: dict[complex, dict[int, list[tuple[str, tuple[int, ...]]]]] = {
        s: {} for s in syndromes
    }
    for ts, moment in enumerate(rnd):
        for gate, targets in moment:
            for t in targets:
                if isinstance(t, tuple):
                    a, b = t
                    s = a if _is_syndrome(a) else b
                    dq = b if _is_syndrome(a) else a
                    corner = _DIR_TO_CORNER[dq - s]
                    pair = (_SYNDROME, corner) if a == s else (corner, _SYNDROME)
                    per_syn.setdefault(s, {}).setdefault(ts, []).append((gate, pair))
                elif _is_syndrome(t):
                    per_syn.setdefault(t, {}).setdefault(ts, []).append((gate, (_SYNDROME,)))
                else:
                    for dirc, corner in _DIR_TO_CORNER.items():
                        s = t - dirc
                        if s in syndromes:
                            per_syn[s].setdefault(ts, []).append((gate, (corner,)))
    return per_syn


def _plaquette_from_local_ops(
    ops_by_ts: dict[int, list[tuple[str, tuple[int, ...]]]], name: str
) -> Plaquette:
    q = SquarePlaquetteQubits()
    circ = stim.Circuit()
    schedule: list[int] = []
    for i, ts in enumerate(sorted(ops_by_ts)):
        if i > 0:
            circ.append("TICK", [], [])
        for gate, idxs in ops_by_ts[ts]:
            circ.append(gate, list(idxs), [])
        schedule.append(ts)
    scheduled = ScheduledCircuit.from_circuit(circ, schedule, q.qubit_map)
    return Plaquette(name, q, scheduled, mergeable_instructions=_MERGEABLE)


def _canonical_key(ops_by_ts: dict[int, list[tuple[str, tuple[int, ...]]]]):
    return tuple((ts, tuple(sorted(ops_by_ts[ts]))) for ts in sorted(ops_by_ts))


def _round_moment_list(distance: int, top: Basis, kind: RoundKind, reverse: bool) -> Round:
    if kind == "switch":
        rnd = _transition_round(distance, top)
    else:
        patch = _degenerate_patch(distance, top)
        mdb = _final_measure_data_basis(patch.data_set, top) if kind == "final" else None
        rnd = _standard_round(patch, mdb)
    return _time_reverse(rnd) if reverse else rnd


def _cell(m: complex) -> tuple[int, int]:
    return round(m.imag + 0.5), round(m.real + 0.5)  # (row, col)


@cache
def _role_map(top: Basis, kind: RoundKind, reverse: bool):
    """Return ``(index_of_key, plaquette_of_index)`` -- a fixed role->index mapping over all k.

    Built from the union of roles at k=1,2,3 (the role set stabilises at k>=2).
    """
    keys: dict = {}
    for k in (1, 2, 3):
        rnd = _round_moment_list(2 * k + 1, top, kind, reverse)
        for ops in _decompose_round(rnd).values():
            keys.setdefault(_canonical_key(ops), ops)
    index_of = {}
    plaq_of = {}
    for i, key in enumerate(sorted(keys, key=repr), start=1):
        index_of[key] = i
        name = f"y_{top}_{kind}_{'r' if reverse else 'f'}_{i}"
        plaq_of[i] = _plaquette_from_local_ops(keys[key], name)
    return index_of, plaq_of


# --------------------------------------------------------------------------------------------
# Scalable template + plaquettes for one Y round
# --------------------------------------------------------------------------------------------
class _YRoundTemplate(RectangularTemplate):
    """A ``RectangularTemplate`` whose plaquette layout is one Y half-cube round."""

    def __init__(self, top: Basis, kind: RoundKind, reverse: bool) -> None:
        super().__init__()
        self._top = top
        self._kind = kind
        self._reverse = reverse

    @property
    def _cells_and_keys(self):
        # cannot cache on k here; computed per instantiate
        raise NotImplementedError

    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        index_of, _ = _role_map(self._top, self._kind, self._reverse)
        if plaquette_indices is None:
            plaquette_indices = list(range(1, self.expected_plaquettes_number + 1))
        distance = 2 * k + 1
        rnd = _round_moment_list(distance, self._top, self._kind, self._reverse)
        shape = self.shape(k).to_numpy_shape()
        ret = numpy.zeros(shape, dtype=numpy.int_)
        for s, ops in _decompose_round(rnd).items():
            row, col = _cell(s)
            ret[row, col] = plaquette_indices[index_of[_canonical_key(ops)] - 1]
        return ret

    @property
    def kind(self) -> RoundKind:
        """The Y round this template lays out (``switch`` carries the logical observable)."""
        return self._kind

    @property
    def top(self) -> Basis:
        """The top boundary basis of the Y half cube this round belongs to."""
        return self._top

    @property
    def scalable_shape(self) -> PlaquetteScalable2D:
        return PlaquetteScalable2D(LinearFunction(2, 2), LinearFunction(2, 2))

    @property
    def expected_plaquettes_number(self) -> int:
        index_of, _ = _role_map(self._top, self._kind, self._reverse)
        return len(index_of)

    def get_border_indices(self, border: TemplateBorder) -> BorderIndices:
        raise TQECError("The Y half cube has no spatial pipes; get_border_indices is not defined.")


# The canonical "no plaquette" filling empty template cells (index 0). It must be *identical* to
# the empty plaquette produced by the ordinary RPNG generator path (translator + identity
# compiler), otherwise merging a Y half cube in parallel with a normal cube raises "several
# different default factories" when combining their ``Plaquettes`` default values.
_EMPTY_PLAQUETTE = IdentityPlaquetteCompiler.compile(
    DefaultRPNGTranslator().translate(RPNGDescription.empty())
)


def _y_round_plaquettes(top: Basis, kind: RoundKind, reverse: bool) -> Plaquettes:
    _, plaq_of = _role_map(top, kind, reverse)
    return Plaquettes(FrozenDefaultDict(dict(plaq_of), default_value=_EMPTY_PLAQUETTE))


# --------------------------------------------------------------------------------------------
# Block assembly
# --------------------------------------------------------------------------------------------
def _round_layer(top: Basis, kind: RoundKind, reverse: bool) -> PlaquetteLayer:
    return PlaquetteLayer(
        _YRoundTemplate(top, kind, reverse), _y_round_plaquettes(top, kind, reverse)
    )


def get_y_half_cube_block(
    y_spec: YHalfCubeSpec, pad_repetitions: LinearFunction | None = None
) -> Block:
    """Build the fixed-bulk Y half-cube as a native Templates/Plaquettes :class:`Block`.

    The measurement half cube is ``[SWITCH, PAD x pad_repetitions, FINAL]`` (one transition round,
    ``pad_repetitions`` padding rounds on the degenerate patch, one data-readout round); the
    initialization half cube is its exact time reverse. Detectors are recovered downstream by
    ``tqecd``.

    Args:
        y_spec: the Y half-cube specification (orientation and init/measure role).
        pad_repetitions: number of degenerate-patch PAD rounds. Unlike the generic HOLD/idle, the
            PAD is *specific to the Y half cube* -- it is the timelike-error suppression of the
            transition. Defaults to ``d // 2 = k`` (``LinearFunction(1, 0)``), the minimum for full
            distance (``ceil(d/2)`` effective rounds including FINAL) and hence the best LER for a
            standalone Y memory. Compilation overrides it with the shared ``block_temporal_height``
            so the half cube's temporal footprint matches neighbouring cubes it may be merged with
            in parallel (see ``FixedBulkCubeBuilder``); this is the same controllable temporal
            height used for ordinary cubes' memory rounds. A constant value must be at least 1.

    Raises:
        ValueError: if ``pad_repetitions`` is a constant smaller than 1.

    """
    top: Basis = "X" if y_spec.horizontal_boundary_basis == TQECBasis.X else "Z"
    # PAD default = distance // 2 = k rounds (ceil(d/2) effective, counting the FINAL round).
    padding = pad_repetitions if pad_repetitions is not None else LinearFunction(1, 0)
    if padding.slope == 0 and padding.offset < 1:
        raise ValueError(f"The Y half cube needs at least one PAD round, got {padding}.")
    # The transition (SWITCH) round is the *connected* temporal border of the half cube; it must
    # sit directly on top of the neighbouring cube's held state. The neighbour's final layer is
    # stripped and its state fed straight into SWITCH by the temporal-pipe composition (see
    # ``TopologicalComputationGraph._replace_temporal_borders``). We therefore emit *no* HOLD/idle
    # round here (hold = 0): closing SWITCH tight against the neighbour keeps the twist adjacent to
    # the code it transforms, which the detector search needs and which minimises the LER. A
    # non-zero hold would be an idle that *preserves* the neighbour's state (repeated stalled
    # rounds), used only to (1) probe robustness of a standalone Y memory or (2) temporally
    # separate the Y cross-line twist from spatially-adjacent braiding blocks; that idling is a
    # generic block concern, not baked into the transition here.
    if y_spec.initialization:
        # data init (open Z-), reverse padding, then the reverse transition at the connected Z+.
        layers: list[BaseLayer | BaseComposedLayer] = [
            _round_layer(top, "final", True),
            RepeatedLayer(_round_layer(top, "pad", True), repetitions=padding),
            _round_layer(top, "switch", True),
        ]
    else:
        # the transition at the connected Z- border, then padding and data readout (open Z+).
        # The first PAD round follows SWITCH, so its detectors differ from later PAD rounds,
        # which only follow other PAD rounds. A ``REPEAT`` body carries the detectors of its first
        # iteration, so the first PAD round is emitted outside of the repetition. Wrapping it in
        # the same middle layer keeps the temporal schedule of an ordinary cube, which is needed to
        # merge the half cube with cubes in parallel.
        layers = [
            _round_layer(top, "switch", False),
            SequencedLayers(
                [
                    _round_layer(top, "pad", False),
                    RepeatedLayer(_round_layer(top, "pad", False), repetitions=padding - 1),
                ]
            ),
            _round_layer(top, "final", False),
        ]
    return Block(layers)


# --------------------------------------------------------------------------------------------
# Logical observable (Y midline)
# --------------------------------------------------------------------------------------------
def _y_observable_measure_qubits(distance: int, top: Basis) -> set[complex]:
    """Patch-coordinate measure qubits whose SWITCH-round measurements form the Y logical.

    Ported from the gen observable flow (y_basis.py): the single-corner ``MY`` plus the
    upper-right and lower-left quadrant stabiliser measurements that compose the two orthogonal
    midline operators crossing at the centre.
    """
    start = _qubit_patch(distance, top)
    end = _degenerate_patch(distance, top)
    used = start.used_set | end.used_set

    def _m_basis(m: complex) -> Basis | None:
        if m.real % 1 == 0:
            return None
        return _checkerboard_basis(m, "Z")

    xs = {q for q in used if _m_basis(q) == "X"}
    zs = {q for q in used if _m_basis(q) == "Z"}
    top_row = {q for q in used if q.imag == -0.5}
    left_col = {q for q in used if q.real == -0.5}
    half_d = distance // 2
    mset_ur = xs if top == "Z" else zs
    mset_dl = xs if top == "X" else zs
    my_target = complex(0, distance - 1) if top == "X" else complex(distance - 1, 0)
    qubits = {my_target}
    qubits |= {q for q in (mset_ur | top_row) if q.real > half_d and q.imag < half_d}
    qubits |= {q for q in (mset_dl | left_col) if q.real < half_d and q.imag > half_d}
    return qubits


def y_observable_local_coords(distance: int, top: Basis) -> list[tuple[float, float]]:
    """Observable-builder local coordinates of the Y-logical measurements in the transition round.

    The observable-builder local convention places the top-left corner at ``(0,0)`` with data
    qubits at integer and measure qubits at half-integer coordinates, which is the patch
    coordinate system shifted by ``(1, 1)``.
    """
    return [(q.real + 1.0, q.imag + 1.0) for q in _y_observable_measure_qubits(distance, top)]


def y_corner_local_coord(distance: int, top: Basis) -> tuple[float, float]:
    """Observable-builder local coordinate of the single-corner ``MY`` data qubit.

    Measured only by the measurement half cube (the initialization half cube resets it), so it
    distinguishes the readout end of a Y memory.
    """
    my_target = complex(0, distance - 1) if top == "X" else complex(distance - 1, 0)
    return (my_target.real + 1.0, my_target.imag + 1.0)
