import pytest
import stim

from tqec import Basis, compile_block_graph
from tqec.gallery import memory
from tqec.interop.crumble import crumble_url_to_circuit
from tqec.utils.exceptions import TQECError

_PREFIX = "https://algassert.com/crumble#circuit="


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("QUBIT_COORDS(0.5, -1) 0\nQUBIT_COORDS(2, 3) 1\nH 0\nCX 0 1", id="coords"),
        pytest.param("R 0 1\nSQRT_X_DAG 0\nSQRT_Y_DAG 1\nS_DAG 0\nSQRT_Z_DAG 1", id="dagger"),
        pytest.param("SQRT_XX 0 1\nSQRT_XX_DAG 0 1\nSQRT_ZZ 0 1\nSQRT_ZZ_DAG 0 1", id="sqrt-pairs"),
        pytest.param("H_XY 0\nH_YZ 1\nH_NXY 0\nH_NXZ 1\nH_NYZ 0", id="hadamard-likes"),
        pytest.param("C_XYZ 0\nC_NXYZ 0\nC_XNYZ 0\nC_XYNZ 0", id="third-turns-xyz"),
        pytest.param("C_ZYX 0\nC_NZYX 0\nC_ZNYX 0\nC_ZYNX 0", id="third-turns-zyx"),
        pytest.param("MR 0\nMPP X0*Z1\nMPP(0.01) Y0*Y1 Z2", id="mpp"),
        pytest.param(
            "R 0 1\nM 0 1\nDETECTOR(1, 2, 3) rec[-1] rec[-2]\nOBSERVABLE_INCLUDE(2) rec[-1]\n"
            "SHIFT_COORDS(0, 0, 1)",
            id="annotations",
        ),
        pytest.param("R 0\nTICK\nREPEAT 3 {\n    H 0\n    TICK\n}\nM 0", id="repeat"),
        pytest.param(
            "X_ERROR(0.1) 0\nZ_ERROR(0.1) 0\nDEPOLARIZE1(0.1) 0\nDEPOLARIZE2(0.1) 0 1\n"
            "CORRELATED_ERROR(0.1) X0 Z1",
            id="noise",
        ),
    ],
)
def test_round_trip_of_stim_url(text: str) -> None:
    circuit = stim.Circuit(text)
    assert crumble_url_to_circuit(circuit.to_crumble_url()) == circuit


def test_every_replacement_is_applied() -> None:
    url = _PREFIX + "Q(1,2)0;DT(0)rec[-1];OI(1)rec[-1];SHIFT_COORDS(1);X_ERROR(0.1)0;SQRT_X_DAG_0"
    assert crumble_url_to_circuit(url) == stim.Circuit(
        "QUBIT_COORDS(1,2) 0\nDETECTOR(0) rec[-1]\nOBSERVABLE_INCLUDE(1) rec[-1]\n"
        "SHIFT_COORDS(1)\nX_ERROR(0.1) 0\nSQRT_X_DAG 0"
    )


def test_crumble_only_instructions_are_dropped() -> None:
    url = (
        _PREFIX
        + "Q(0,0)0;R_0;POLYGON(1,0,0,0.5)0_1_2;MARK_0;MARKX(1)0;MARKY_0;MARKZ_0;ERR_0;"
        + "#!pragma_ERR_0;#!pragma_MARK_0;#!pragma_POLYGON(1,0,0,0.5)0_1;M_0"
    )
    assert crumble_url_to_circuit(url) == stim.Circuit("QUBIT_COORDS(0,0) 0\nR 0\nM 0")


def test_fragment_only_and_percent_encoding_and_other_parameters() -> None:
    expected = stim.Circuit("H 0\nM 0")
    assert crumble_url_to_circuit("#circuit=H_0;M_0") == expected
    assert crumble_url_to_circuit(_PREFIX + "H_0%3BM_0") == expected
    assert crumble_url_to_circuit("https://algassert.com/crumble#x=1&circuit=H_0;M_0") == expected


def test_url_with_polygons_from_tqec() -> None:
    graph = compile_block_graph(memory(Basis.Z))
    with_polygons = crumble_url_to_circuit(graph.generate_crumble_url(1, add_polygons=True))
    assert "POLYGON" in graph.generate_crumble_url(1, add_polygons=True)
    without_polygons = crumble_url_to_circuit(graph.generate_crumble_url(1, add_polygons=False))
    assert with_polygons == without_polygons
    assert with_polygons.num_detectors > 0


@pytest.mark.parametrize(
    "url",
    [
        "",
        "H 0",
        "https://example.com/crumble#circuit=H_0",
        "https://algassert.com/crumble",
        "https://algassert.com/crumble#x=1",
        "https://algassert.com/crumble#circuit=NOT_A_GATE_0_1_2(",
        "https://algassert.com/crumble#circuit=H_a",
    ],
)
def test_not_a_crumble_url_or_circuit_raises(url: str) -> None:
    with pytest.raises(TQECError):
        crumble_url_to_circuit(url)
