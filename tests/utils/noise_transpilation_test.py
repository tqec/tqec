"""Tests for :func:`tqec.utils.noise_transpilation.transpile_to_si1000_gateset`.

On this branch the SI1000 gate-set transpiler is a not-yet-implemented stub: the working
implementation (delegating to ``stimflow``) was moved to the ``kd/si1000-transpilation`` branch so
``kd/dae-batch-processing`` does not carry a git-subdirectory dependency on an unreleased Stim fork
sub-package. The transpiler must therefore fail loudly rather than silently produce a wrong
circuit. It is not exported from ``tqec``; ``tqec.orchestration.simulate`` imports it from its
module and raises the ``NotImplementedError`` only when ``si1000`` is actually requested.
"""

import re

import pytest
import stim

from tqec.utils.noise_transpilation import transpile_to_si1000_gateset


# replace this with a unit test when the transpiler
# is implemented
def test_transpiler_raises_not_implemented() -> None:
    circuit = stim.Circuit("RX 0\nMX 0")
    with pytest.raises(NotImplementedError, match=re.escape("not implemented yet")):
        transpile_to_si1000_gateset(circuit)
