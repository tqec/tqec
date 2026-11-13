"""Decodes a Crumble URL into the ``stim`` circuit it contains."""

import re
from urllib.parse import unquote

import stim

from tqec.utils.exceptions import TQECError

_CRUMBLE_URL_PREFIXES = ("https://algassert.com/crumble#", "#")

# The text replacements of ``Circuit.fromStimCircuit`` in ``glue/crumble/circuit/circuit.js`` of the
# stim repository (checked at commit 131793efb), in the order in which Crumble applies them.
_CRUMBLE_REPLACEMENTS = (
    (";", "\n"),
    ("#!pragma ERR", "ERR"),
    ("#!pragma MARK", "MARK"),
    ("#!pragma POLYGON", "POLYGON"),
    ("_", " "),
    ("Q(", "QUBIT_COORDS("),
    ("DT", "DETECTOR"),
    ("OI", "OBSERVABLE_INCLUDE"),
    (" COORDS", "_COORDS"),
    (" ERROR", "_ERROR"),
    ("C XYZ", "C_XYZ"),
    ("C NXYZ", "C_NXYZ"),
    ("C XNYZ", "C_XNYZ"),
    ("C XYNZ", "C_XYNZ"),
    ("H XY", "H_XY"),
    ("H XZ", "H_XZ"),
    ("H YZ", "H_YZ"),
    ("H NXY", "H_NXY"),
    ("H NXZ", "H_NXZ"),
    ("H NYZ", "H_NYZ"),
    (" INCLUDE", "_INCLUDE"),
    ("SQRT ", "SQRT_"),
    (" DAG ", "_DAG "),
    ("C ZYX", "C_ZYX"),
    ("C NZYX", "C_NZYX"),
    ("C ZNYX", "C_ZNYX"),
    ("C ZYNX", "C_ZYNX"),
)

# Instructions that only exist in Crumble, and that ``stim`` cannot parse.
_CRUMBLE_ONLY_INSTRUCTIONS = frozenset({"POLYGON", "MARK", "MARKX", "MARKY", "MARKZ", "ERR"})
_INSTRUCTION_NAME_RE = re.compile(r"\s*([^\s(\[]*)")


def _crumble_circuit_text(url: str) -> str:
    """Return the value of the ``circuit`` parameter in the fragment of ``url``."""
    for prefix in _CRUMBLE_URL_PREFIXES:
        if url.startswith(prefix):
            break
    else:
        raise TQECError(
            "Expected a Crumble URL starting with 'https://algassert.com/crumble#circuit=', "
            f"got '{url[:60]}'."
        )
    # Crumble splits the fragment on ``&`` into ``key=value`` pairs and percent-decodes each value.
    for key_value in url.removeprefix(prefix).split("&"):
        key, equal, value = key_value.partition("=")
        if equal and key == "circuit":
            return unquote(value)
    raise TQECError(f"The Crumble URL has no 'circuit=' parameter: '{url[:60]}'.")


def _instruction_name(line: str) -> str:
    """Return the name of the instruction on ``line``, or an empty string."""
    match = _INSTRUCTION_NAME_RE.match(line)
    return match.group(1) if match else ""


def crumble_url_to_circuit(url: str) -> stim.Circuit:
    """Return the ``stim`` circuit encoded in a Crumble URL.

    This is the inverse of :meth:`stim.Circuit.to_crumble_url`, and decodes the URLs that
    :meth:`~tqec.compile.graph.TopologicalComputationGraph.generate_crumble_url` returns. The URL
    is read like Crumble does: all the text replacements of ``Circuit.fromStimCircuit`` in
    ``glue/crumble/circuit/circuit.js`` of the `stim repository <https://github.com/quantumlib/Stim>`_
    (checked at commit ``131793efb``) are applied in the same order, so that, for example,
    ``Q(0,1)0`` becomes ``QUBIT_COORDS(0,1) 0`` and ``SQRT_X_DAG`` is read back from
    ``SQRT_X_DAG``.

    The instructions that exist only in Crumble and that ``stim`` cannot hold are dropped: the
    annotations ``POLYGON``, ``MARK``, ``MARKX``, ``MARKY`` and ``MARKZ`` and the ``ERR`` gate (also
    when written as a ``#!pragma`` line). Everything else is kept, including the noise channels
    and ``SHIFT_COORDS`` that Crumble itself ignores when it draws the circuit. Instructions that
    Crumble does not know are not dropped, so ``stim`` rejects those it cannot parse.

    The URL must start with ``https://algassert.com/crumble#`` (or be only the fragment,
    ``#circuit=...``, as Crumble reads ``document.location.hash``) and contain a ``circuit``
    parameter. A percent-encoded value is decoded, as Crumble does.

    Args:
        url: the Crumble URL, for instance ``https://algassert.com/crumble#circuit=H_0;M_0``.

    Returns:
        the circuit that ``url`` encodes.

    Raises:
        TQECError: if ``url`` is not a Crumble URL, has no ``circuit`` parameter, or its circuit
            text is not valid ``stim`` text once decoded.

    """
    text = _crumble_circuit_text(url)
    for short, full in _CRUMBLE_REPLACEMENTS:
        text = text.replace(short, full)
    lines = [
        line
        for line in text.split("\n")
        if _instruction_name(line) not in _CRUMBLE_ONLY_INSTRUCTIONS
    ]
    # Crumble accepts ``QUBIT_COORDS(0,0)0``; stim needs a space before the first target.
    text = re.sub(r"\)(?=\S)", ") ", "\n".join(lines))
    try:
        return stim.Circuit(text)
    except (ValueError, RuntimeError) as exception:
        raise TQECError(
            f"The Crumble URL does not contain a valid stim circuit: {exception}"
        ) from exception
