from unittest.mock import MagicMock

import pytest
import sinter
import stim

from tqec.computation.block_graph import BlockGraph
from tqec.simulation.threshold import binary_search_threshold
from tqec.utils.exceptions import TQECError
from tqec.utils.noise_model import NoiseModel


@pytest.fixture
def mock_collect(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock circuit compilation and sampling to test search decisions."""
    compiled_graph = MagicMock()
    compiled_graph.generate_stim_circuit.return_value = stim.Circuit()
    monkeypatch.setattr(
        "tqec.simulation.threshold.compile_block_graph", MagicMock(return_value=compiled_graph)
    )
    collect = MagicMock()
    monkeypatch.setattr("tqec.simulation.threshold.sinter.collect", collect)
    return collect


@pytest.mark.parametrize("errors", [(0, 0), (0, 10), (10, 0)])
def test_binary_search_threshold_zero_errors(
    mock_collect: MagicMock, errors: tuple[int, int]
) -> None:
    mock_collect.return_value = [
        sinter.TaskStats(
            strong_id=str(distance),
            decoder="pymatching",
            json_metadata={"d": distance},
            shots=1000,
            errors=error_count,
        )
        for distance, error_count in zip((3, 5), errors)
    ]

    with pytest.raises(TQECError, match="more shots"):
        binary_search_threshold(
            BlockGraph(), MagicMock(), NoiseModel.uniform_depolarizing, max_shots=1000
        )
    mock_collect.assert_called_once()


@pytest.mark.parametrize("best", [None, float("nan"), float("inf"), -float("inf")])
def test_binary_search_threshold_invalid_estimate(
    mock_collect: MagicMock, monkeypatch: pytest.MonkeyPatch, best: float | None
) -> None:
    mock_collect.return_value = [
        sinter.TaskStats(str(distance), decoder="pymatching", json_metadata={"d": distance})
        for distance in (3, 5)
    ]
    monkeypatch.setattr(
        "tqec.simulation.threshold.get_logical_error_rate_per_shot",
        MagicMock(return_value=sinter.Fit(low=0, best=best, high=1)),
    )

    with pytest.raises(TQECError, match="more shots"):
        binary_search_threshold(BlockGraph(), MagicMock(), NoiseModel.uniform_depolarizing)
    mock_collect.assert_called_once()


@pytest.mark.parametrize(
    "errors,expected", [((10, 20), 0.125), ((20, 10), 0.175), ((600, 500), 0.125)]
)
def test_binary_search_threshold_finite_estimates(
    mock_collect: MagicMock, errors: tuple[int, int], expected: float
) -> None:
    mock_collect.return_value = [
        sinter.TaskStats(
            strong_id=str(distance),
            decoder="pymatching",
            json_metadata={"d": distance},
            shots=1000,
            errors=error_count,
        )
        for distance, error_count in zip((3, 5), errors)
    ]

    result, fits = binary_search_threshold(
        BlockGraph(),
        MagicMock(),
        NoiseModel.uniform_depolarizing,
        minp=0.1,
        maxp=0.2,
        atol=0.06,
    )

    assert result == pytest.approx(expected)
    assert all(len(values) == 1 for values in fits.values())
    mock_collect.assert_called_once()
