import pytest
import stim

from tqec.circuit.surface_code_layout import (
    StabilizerCheck,
    SurfaceCodeLayout,
    surface_code_memory_layout,
)
from tqec.utils.exceptions import TQECError


def test_layout_of_a_distance_two_style_patch() -> None:
    circuit = stim.Circuit("""
        QUBIT_COORDS(1, 1) 0
        QUBIT_COORDS(3, 1) 1
        QUBIT_COORDS(2, 0) 2
        QUBIT_COORDS(2, 2) 3
        RX 2
        R 0 1 3
        TICK
        CX 2 0 1 3
        CZ 3 0
        TICK
        MX 2
        M 3
        TICK
        MX 2
        M 3 0 1
    """)
    layout = surface_code_memory_layout(circuit)
    assert layout == SurfaceCodeLayout(
        data_qubits=frozenset({(1.0, 1.0), (3.0, 1.0)}),
        checks={
            (2.0, 0.0): StabilizerCheck("X", frozenset({(1.0, 1.0)})),
            (2.0, 2.0): StabilizerCheck("Z", frozenset({(3.0, 1.0), (1.0, 1.0)})),
        },
    )
    data, checks = layout
    assert data == layout.data_qubits
    assert checks[(2.0, 0.0)].basis == "X"


@pytest.mark.parametrize("basis", ["x", "z"])
def test_layout_of_the_stim_rotated_memory(basis: str) -> None:
    circuit = stim.Circuit.generated(f"surface_code:rotated_memory_{basis}", distance=3, rounds=2)
    data, checks = surface_code_memory_layout(circuit)
    assert len(data) == 9
    assert len(checks) == 8
    assert {c.basis for c in checks.values()} == {"X", "Z"}
    assert all(len(c.support) in (2, 4) for c in checks.values())


_VALID = """
    QUBIT_COORDS(0, 0) 0
    QUBIT_COORDS(1, 0) 1
    R 0 1
    {first_round}
    MR 1
    MR 1
    M 0
"""


def _circuit(first_round: str = "CX 1 0", header: str = "") -> stim.Circuit:
    return stim.Circuit(header + _VALID.format(first_round=first_round))


def test_valid_minimal_circuit() -> None:
    data, checks = surface_code_memory_layout(_circuit())
    assert data == {(0.0, 0.0)}
    assert checks == {(1.0, 0.0): StabilizerCheck("X", frozenset({(0.0, 0.0)}))}


@pytest.mark.parametrize(
    ("circuit", "message"),
    [
        pytest.param(
            stim.Circuit("QUBIT_COORDS(0, 0) 0\nR 0 2\nCX 0 2\nMR 2\nMR 2\nM 0"),
            "have no QUBIT_COORDS",
            id="missing-coords",
        ),
        pytest.param(
            stim.Circuit("QUBIT_COORDS(0) 0\nQUBIT_COORDS(1, 0) 1\nCX 1 0\nMR 1\nMR 1\nM 0"),
            "fewer than two coordinates",
            id="one-coordinate",
        ),
        pytest.param(
            stim.Circuit(
                "QUBIT_COORDS(0, 0, 0) 0\nQUBIT_COORDS(0, 0, 1) 1\nCX 1 0\nMR 1\nMR 1\nM 0"
            ),
            "share the same",
            id="duplicate-xy",
        ),
        pytest.param(
            stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 0) 1\nCX 1 0\nMR 1\nM 0"),
            "at least two rounds",
            id="single-round",
        ),
        pytest.param(_circuit("CY 1 0"), "only CX or CZ", id="other-gate"),
        pytest.param(_circuit("SWAP 1 0"), "only CX or CZ", id="swap"),
        pytest.param(
            stim.Circuit(
                "QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 0) 1\nQUBIT_COORDS(2, 0) 2\n"
                "CX 1 0 0 2\nMR 1\nMR 1\nM 0 2"
            ),
            "one data qubit and one measure qubit",
            id="neither-is-measure-qubit",
        ),
        pytest.param(_circuit("CX 1 0\nCX rec[-1] 0"), "non-qubit target", id="feedback-target"),
    ],
)
def test_layout_errors(circuit: stim.Circuit, message: str) -> None:
    with pytest.raises(TQECError, match=message):
        surface_code_memory_layout(circuit)


def test_unused_qubits_are_ignored() -> None:
    header = "QUBIT_COORDS(5) 98\nQUBIT_COORDS(0, 0) 99\n"
    assert surface_code_memory_layout(_circuit(header=header)) == surface_code_memory_layout(
        _circuit()
    )
