"""Reads the layout of a surface code memory experiment from its ``stim`` circuit."""

from collections import Counter
from typing import NamedTuple

import stim

from tqec.utils.exceptions import TQECError

Point = tuple[float, float]
"""An ``(x, y)`` position given by ``QUBIT_COORDS``."""


class StabilizerCheck(NamedTuple):
    """A stabilizer check read from a circuit."""

    basis: str
    """Basis of the check, ``"X"`` or ``"Z"``."""
    support: frozenset[Point]
    """Positions of the data qubits that the check acts on."""


class SurfaceCodeLayout(NamedTuple):
    """The data qubits and the stabilizer checks of a surface code circuit."""

    data_qubits: frozenset[Point]
    """Positions of the data qubits."""
    checks: dict[Point, StabilizerCheck]
    """Check of each measure qubit, by position of the measure qubit."""


def surface_code_memory_layout(circuit: stim.Circuit) -> SurfaceCodeLayout:
    """Return the data qubit positions and, per measure qubit position, its check basis and support.

    Data qubits are the qubits measured exactly once (at the end); measure qubits are measured
    every round. Stabilizers are read from the two-qubit gates of the first round: ``CZ`` or a
    ``CX`` targeting the measure qubit is a Z check, a ``CX`` controlled by it an X check.
    Qubits that only appear in ``QUBIT_COORDS`` are ignored. Only the ``x`` and ``y`` coordinates
    are read.

    This only reads a surface code memory experiment, like the ones that tqec compiles from
    :func:`tqec.gallery.memory` or that ``stim.Circuit.generated("surface_code:rotated_memory_z")``
    returns. It assumes that:

    - every qubit has ``QUBIT_COORDS``, and no two qubits share the same ``(x, y)``;
    - the circuit has at least two rounds, data qubits are measured only once (no mid-circuit
      data measurement, as in lattice surgery) and each check has its own measure qubit (no
      flag qubit);
    - the two-qubit gates before the first measurement of a measure qubit are exactly the first
      round, and each of them acts on one data qubit and one measure qubit;
    - the two-qubit gates are ``CX`` or ``CZ``, a measure qubit used as ``CZ`` or ``CX`` control
      is reset and measured in the X basis (``RX``/``MX``, or ``H`` around ``R``/``M``) and one
      used as ``CX`` target in the Z basis (resets, measurements and ``H`` are not read), and no
      single-qubit gate acts on a data qubit during the round.

    The first assumption, that there are at least two rounds, that each two-qubit gate of the
    first round acts on one data qubit and one measure qubit, and that these gates are ``CX`` or
    ``CZ`` are checked. The other assumptions are not: the basis of a check is deduced from the
    gates only, a flag qubit or a data qubit measured mid-circuit is read as a measure or a data
    qubit according to how often it is measured, and a circuit that breaks them can give a wrong
    layout without an error.

    Args:
        circuit: a surface code memory circuit that satisfies the assumptions above.

    Returns:
        the positions of the data qubits and the check of each measure qubit.

    Raises:
        TQECError: if a qubit used by an instruction has no ``QUBIT_COORDS`` or fewer than two
            coordinates, if two qubits share the same ``(x, y)``, if no qubit is measured more
            than once, or if a two-qubit gate of the first round is not a ``CX`` or ``CZ``, or
            does not act on one data qubit and one measure qubit.

    """
    coords_by_qubit = circuit.get_final_qubit_coordinates()
    short = [q for q, c in coords_by_qubit.items() if len(c) < 2]
    if short:
        raise TQECError(f"Qubits {short} have fewer than two coordinates.")
    coords = {q: (c[0], c[1]) for q, c in coords_by_qubit.items()}
    if len(set(coords.values())) != len(coords):
        raise TQECError("Two qubits share the same (x, y) coordinates.")
    flat = [inst for inst in circuit.flattened() if isinstance(inst, stim.CircuitInstruction)]
    no_coords = sorted(
        {
            t.qubit_value
            for inst in flat
            for t in inst.targets_copy()
            if t.qubit_value is not None and t.qubit_value not in coords
        }
    )
    if no_coords:
        raise TQECError(f"Qubits {no_coords} have no QUBIT_COORDS.")
    measured = Counter(
        t.value
        for inst in flat
        if stim.gate_data(inst.name).produces_measurements
        for t in inst.targets_copy()
    )
    measure_qubits = {q for q, n in measured.items() if n > 1}
    if not measure_qubits:
        raise TQECError("No qubit is measured more than once: at least two rounds are needed.")
    data = {coords[q] for q, n in measured.items() if n == 1}
    checks: dict[int, tuple[str, set[Point]]] = {}
    for inst in flat:
        if stim.gate_data(inst.name).produces_measurements and any(
            t.value in measure_qubits for t in inst.targets_copy()
        ):
            break
        gate = stim.gate_data(inst.name)
        if not gate.is_two_qubit_gate or gate.is_noisy_gate:
            continue
        if inst.name not in ("CX", "CZ"):
            raise TQECError(f"Expected only CX or CZ in the first round, got {inst.name}.")
        for control, target in inst.target_groups():
            if not (control.is_qubit_target and target.is_qubit_target):
                raise TQECError(f"{inst.name} with a non-qubit target in the first round.")
            c, t = control.value, target.value
            if (c in measure_qubits) == (t in measure_qubits):
                raise TQECError(
                    f"{inst.name} {c} {t} in the first round is not between one data qubit and "
                    "one measure qubit."
                )
            m, d = (c, t) if c in measure_qubits else (t, c)
            basis = "X" if inst.name == "CX" and m == c else "Z"
            checks.setdefault(m, (basis, set()))[1].add(coords[d])
    return SurfaceCodeLayout(
        frozenset(data),
        {coords[m]: StabilizerCheck(b, frozenset(ds)) for m, (b, ds) in checks.items()},
    )
