"""Tests for :func:`tqec.transpile_to_si1000_gateset`.

On this branch the SI1000 gate-set transpiler is a not-yet-implemented stub: the working
implementation (delegating to ``stimflow``) was moved to the ``kd/si1000-transpilation`` branch so
``kd/dae-batch-processing`` does not carry a git-subdirectory dependency on an unreleased Stim fork
sub-package. The transpiler must therefore fail loudly rather than silently produce a wrong
circuit, and it must stay importable/exported so callers such as ``tqec.orchestration.simulate``
still resolve the symbol (and surface the ``NotImplementedError`` only when ``si1000`` is actually
requested).
"""

import re

import pytest
import stim

import tqec
from tqec.utils.noise_transpilation import transpile_to_si1000_gateset


def test_symbol_is_exported_at_top_level() -> None:
    assert tqec.transpile_to_si1000_gateset is transpile_to_si1000_gateset


def test_transpiler_raises_not_implemented() -> None:
    circuit = stim.Circuit("RX 0\nMX 0")
    with pytest.raises(NotImplementedError, match=re.escape("kd/si1000-transpilation")):
        transpile_to_si1000_gateset(circuit)
