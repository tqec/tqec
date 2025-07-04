import pytest
import stim

from tqec.post_processing.filter import subcircuit_only_on_indices
from tqec.utils.exceptions import TQECWarning


def test_identity() -> None:
    circuit = stim.Circuit("CX 0 1 2 4 5 6 7 8")
    assert subcircuit_only_on_indices(circuit, frozenset(range(9))) == circuit


def test_one_instruction() -> None:
    circuit = stim.Circuit("CX 0 1 2 3 4 5 6 7")
    assert (
        subcircuit_only_on_indices(circuit, frozenset((0, 2, 4, 6))) == stim.Circuit()
    )
    assert subcircuit_only_on_indices(circuit, frozenset(range(4))) == stim.Circuit(
        "CX 0 1 2 3"
    )


def test_non_qubit_targets() -> None:
    circuit = stim.Circuit("M 0 1 2 3 4\nDETECTOR rec[-1] rec[-2]")
    with pytest.warns(
        TQECWarning,
        match="^Found a measurement record target when filtering a circuit.*",
    ):
        assert subcircuit_only_on_indices(
            circuit, frozenset((2, 3, 4))
        ) == stim.Circuit("M 2 3 4\nDETECTOR rec[-1] rec[-2]")

    with pytest.warns(
        TQECWarning,
        match="^Found a measurement record target when filtering a circuit.*",
    ):
        assert subcircuit_only_on_indices(
            stim.Circuit("CX rec[-1] 0\nCX rec[-2] 1"), frozenset((0,))
        ) == stim.Circuit("CX rec[-1] 0")
