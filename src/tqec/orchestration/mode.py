"""Circuit-generation modes for materializing or streaming a circuit to disk.

The prepare stage writes one noiseless ``.stim`` file per ``k``. This module owns *how* that
file is produced, behind a single :func:`write_circuit` entry point so the choice of strategy is
a one-line switch at the call site rather than branching logic inside the batch loop.

Two modes are supported:

* ``"materialized"`` builds the whole circuit in memory
  (:meth:`~tqec.compile.graph.TopologicalComputationGraph.generate_stim_circuit`) before writing it.
* ``"streaming"`` consumes
  (:meth:`~tqec.compile.graph.TopologicalComputationGraph.generate_stim_circuit_stream`), which
  yields the circuit in TICK-aligned slices, and appends each slice's text to the file as it
  arrives, so the full circuit is never held in memory all at once.

The streamed slices concatenate to exactly the materialized circuit (they are the same circuit
cut at TICK boundaries), and stim's text form of the concatenation is the per-slice texts joined
by newlines. Writing each slice's text in order, single-newline separated, therefore reproduces
:meth:`~stim.Circuit.to_file`'s output byte-for-byte. The equivalence test in
``tests/orchestration`` locks this in.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

    import stim

MATERIALIZED = "materialized"
STREAMING = "streaming"
CIRCUIT_MODES = (MATERIALIZED, STREAMING)


class _CircuitSource(Protocol):
    """The narrow slice of a compiled graph that :func:`write_circuit` depends on."""

    def generate_stim_circuit(
        self, k: int, manhattan_radius: int = ...
    ) -> stim.Circuit: ...

    def generate_stim_circuit_stream(
        self,
        k: int,
        noise_model: object = ...,
        manhattan_radius: int = ...,
    ) -> Iterator[stim.Circuit]: ...


def write_circuit(
    compiled: _CircuitSource,
    k: int,
    path: str | Path,
    *,
    mode: str = MATERIALIZED,
    manhattan_radius: int,
) -> None:
    """Generate the noiseless circuit for one ``k`` and write it to ``path``.

    Args:
        compiled: The compiled computation graph to export. Only its
            ``generate_stim_circuit`` / ``generate_stim_circuit_stream`` methods are used.
        k: Scale factor of the templates.
        path: Destination ``.stim`` file. Its parent directory must already exist.
        mode: ``"materialized"`` (default) builds the whole circuit in memory.
            ``"streaming"`` appends the circuit's TICK-aligned slices as they are
            produced, so the full circuit is never all in memory at once. Both modes
            leave identical bytes on disk.
        manhattan_radius: Radius used to automatically compute detectors, forwarded unchanged.

    Raises:
        ValueError: If ``mode`` is not one of ``"materialized"`` / ``"streaming"``.

    """
    target = Path(path)
    if mode == MATERIALIZED:
        compiled.generate_stim_circuit(k, manhattan_radius=manhattan_radius).to_file(
            target
        )
    elif mode == STREAMING:
        _write_streaming(compiled, k, target, manhattan_radius=manhattan_radius)
    else:
        raise ValueError(
            f"Unknown circuit mode {mode!r}; expected one of {', '.join(CIRCUIT_MODES)}."
        )


def _write_streaming(
    compiled: _CircuitSource,
    k: int,
    path: Path,
    *,
    manhattan_radius: int,
) -> None:
    """Append each TICK-aligned circuit slice's text to ``path`` as it is produced.

    The slices are the materialized circuit cut at TICK boundaries, so writing their texts in
    order--single-newline separated, with a trailing newline--reproduces
    :meth:`stim.Circuit.to_file` byte-for-byte without ever holding the whole circuit in memory.
    """
    slices = compiled.generate_stim_circuit_stream(
        k, noise_model=None, manhattan_radius=manhattan_radius
    )
    with path.open("w") as handle:
        wrote_any = False
        for circuit_slice in slices:
            text = str(circuit_slice)
            if not text:
                continue
            if wrote_any:
                handle.write("\n")
            handle.write(text)
            wrote_any = True
        if wrote_any:
            handle.write("\n")
