from collections import Counter
from pathlib import Path

import pytest
import sinter

from tqec.exceptions import TQECException
from tqec.simulation.io_utils.csv_files import write_sinter_stats_to_csv


@pytest.fixture
def stats_a() -> list[sinter.TaskStats]:
    return [
        sinter.TaskStats(
            strong_id="id_a0",
            decoder="pymatching",
            shots=1000_000,
            errors=1000,
            discards=0,
            seconds=2.5,
            json_metadata=dict(d=5, p=0.001, r=5),
            custom_counts=Counter(foo=3, bar=9),
        ),
        sinter.TaskStats(
            strong_id="id_a1",
            decoder="pymatching",
            shots=2000_000,
            errors=1500,
            discards=1,
            seconds=3.7,
            json_metadata=dict(d=7, p=0.01, r=7),
        ),
        sinter.TaskStats(
            strong_id="id_a2",
            decoder="pymatching",
            shots=1000,
            errors=1,
            discards=0,
            seconds=0.1,
            json_metadata=dict(d=9, p=0.0023, r=9),
        ),
    ]


@pytest.fixture
def stats_b() -> list[sinter.TaskStats]:
    return [
        sinter.TaskStats(
            strong_id="id_a0",
            decoder="pymatching",
            shots=10_000_000,
            errors=10_000,
            discards=3,
            seconds=25.0,
            json_metadata=dict(d=5, p=0.001, r=5),
            custom_counts=Counter(foo=10, bar=10),
        ),
        sinter.TaskStats(
            strong_id="id_b0",
            decoder="pymatching",
            shots=2000000,
            errors=1500,
            discards=1,
            seconds=3.7,
            json_metadata=dict(d=7, p=0.01, r=7),
        ),
    ]


def test_write_read_consistent(tmp_path: Path, stats_a: list[sinter.TaskStats]) -> None:
    filepath = tmp_path / "data.csv"
    write_sinter_stats_to_csv(filepath, stats_a)
    stats_from_csv = sinter.read_stats_from_csv_files(filepath)

    assert stats_a == stats_from_csv


def test_raise_if_file_exists(tmp_path: Path, stats_a: list[sinter.TaskStats]) -> None:
    filepath = tmp_path / "data.csv"
    write_sinter_stats_to_csv(filepath, stats_a)

    with pytest.raises(TQECException) as excinfo:
        write_sinter_stats_to_csv(filepath, stats_a, if_file_exists="raise")

    assert "exists" in str(excinfo.value)


def test_overwrite_if_file_exists(
    tmp_path: Path, stats_a: list[sinter.TaskStats], stats_b: list[sinter.TaskStats]
) -> None:
    filepath = tmp_path / "data.csv"
    write_sinter_stats_to_csv(filepath, stats_a)
    write_sinter_stats_to_csv(filepath, stats_b, if_file_exists="overwrite")
    stats_from_csv = sinter.read_stats_from_csv_files(filepath)

    assert stats_from_csv != stats_a
    assert stats_from_csv == stats_b


def test_merge_if_file_exists(
    tmp_path: Path, stats_a: list[sinter.TaskStats], stats_b: list[sinter.TaskStats]
) -> None:
    filepath = tmp_path / "data.csv"
    write_sinter_stats_to_csv(filepath, stats_a)
    write_sinter_stats_to_csv(filepath, stats_b, if_file_exists="merge")
    stats_from_csv = sinter.read_stats_from_csv_files(filepath)

    assert len(stats_from_csv) == 4
    assert next(
        (s for s in stats_from_csv if s.strong_id == "id_a0")
    ) == sinter.TaskStats(
        strong_id="id_a0",
        decoder="pymatching",
        shots=11_000_000,
        errors=11_000,
        discards=3,
        seconds=27.5,
        json_metadata=dict(d=5, p=0.001, r=5),
        custom_counts=Counter(foo=13, bar=19),
    ), "The two entries for `id_a0` should be merged correctly."
