import re

import pytest
import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap, get_qubit_map
from tqec.utils.exceptions import TQECException


def test_qubit_map_creation() -> None:
    q = GridQubit(0, 0)
    QubitMap()
    QubitMap({0: q})
    QubitMap({1: q})

    qset_str = re.escape(str(frozenset([q])))
    with pytest.raises(
        TQECException,
        match=f"^Found qubit\\(s\\) with more than one index: {qset_str}.$",
    ):
        QubitMap({0: q, 1: q})

    QubitMap.from_qubits([])
    QubitMap.from_qubits([GridQubit(0, 0)])
    with pytest.raises(
        TQECException,
        match=f"^Found qubit\\(s\\) with more than one index: {qset_str}.$",
    ):
        QubitMap.from_qubits([q, q])

    QubitMap.from_circuit(stim.Circuit())
    QubitMap.from_circuit(stim.Circuit("H 0"))
    QubitMap.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0"))
    with pytest.raises(
        TQECException,
        match=f"^Found qubit\\(s\\) with more than one index: {qset_str}.$",
    ):
        QubitMap.from_circuit(stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(0, 0) 1"))


def test_qubit_map_getters() -> None:
    assert frozenset(QubitMap().indices) == frozenset()
    assert frozenset(QubitMap().qubits) == frozenset()

    qmap = QubitMap({i: GridQubit(i, -i) for i in range(4)})
    assert frozenset(qmap.indices) == frozenset(range(4))
    assert frozenset(qmap.qubits) == frozenset(GridQubit(i, -i) for i in range(4))


def test_qubit_map_q2i() -> None:
    assert QubitMap().q2i == {}

    qmap = QubitMap({i: GridQubit(i, -i) for i in range(4)})
    assert qmap.q2i == {GridQubit(i, -i): i for i in range(4)}


def test_qubit_map_with_mapped_qubits() -> None:
    qubit_map = {GridQubit(i, -i): GridQubit(-i, i) for i in range(4)}
    assert QubitMap().with_mapped_qubits(lambda q: qubit_map[q]) == QubitMap()

    qmap = QubitMap({i: GridQubit(i, -i) for i in range(4)})
    assert qmap.with_mapped_qubits(lambda q: qubit_map[q]) == QubitMap(
        {i: GridQubit(-i, i) for i in range(4)}
    )


def test_qubit_map_filter_by_qubits() -> None:
    qubits = [GridQubit(i, -i) for i in range(3)]
    assert QubitMap().filter_by_qubits(qubits) == QubitMap()

    qmap = QubitMap({i: GridQubit(i, -i) for i in range(4)})
    assert qmap.filter_by_qubits(qubits) == QubitMap({i: GridQubit(i, -i) for i in range(3)})


def test_get_final_qubits() -> None:
    assert get_qubit_map(stim.Circuit("QUBIT_COORDS(0, 0) 0")) == QubitMap({0: GridQubit(0, 0)})
    assert get_qubit_map(stim.Circuit("QUBIT_COORDS(0, 0) 1")) == QubitMap({1: GridQubit(0, 0)})
    # assert get_final_qubits(
    #     stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 4) 0")
    # ) == {0: GridQubit(1, 4)}
    assert get_qubit_map(stim.Circuit("QUBIT_COORDS(0, 0) 0\nQUBIT_COORDS(1, 4) 1")) == QubitMap(
        {0: GridQubit(0, 0), 1: GridQubit(1, 4)}
    )

    with pytest.raises(
        TQECException,
        match=re.escape(
            "Qubits should be defined on exactly 2 spatial dimensions. "
            f"Found {0} -> [0.0, 0.0, 1.0] defined on 3 spatial dimensions."
        ),
    ):
        get_qubit_map(stim.Circuit("QUBIT_COORDS(0, 0, 1) 0"))


def test_qubit_map_to_circuit() -> None:
    assert QubitMap.from_qubits([GridQubit(0, 0)]).to_circuit() == stim.Circuit(
        "QUBIT_COORDS(0, 0) 0"
    )
    assert QubitMap.from_circuit(
        stim.Circuit("QUBIT_COORDS(0, 0) 0\nH 0")
    ).to_circuit() == stim.Circuit("QUBIT_COORDS(0, 0) 0")


def test_qubit_map_getitem() -> None:
    qmap = QubitMap({i: GridQubit(i, -i) for i in range(10)})
    for i in range(10):
        assert qmap[GridQubit(i, -i)] == i
    with pytest.raises(KeyError):
        qmap[GridQubit(1, 1)]


def test_qubit_map_qubit_bounds() -> None:
    with pytest.raises(TQECException):
        QubitMap({}).qubit_bounds()
    assert QubitMap({0: GridQubit(9, 45)}).qubit_bounds() == (GridQubit(9, 45), GridQubit(9, 45))
    assert QubitMap({i: GridQubit(i, -i) for i in range(10)}).qubit_bounds() == (
        GridQubit(0, -9),
        GridQubit(9, 0),
    )
