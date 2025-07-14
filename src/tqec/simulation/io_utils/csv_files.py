"""Read and write simulation data from and to csv files."""

import io
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, TextIO

import sinter

from tqec.utils.exceptions import TQECError


def write_sinter_stats_to_csv(
    filepath: str | Path,
    stats: Iterable[sinter.TaskStats],
    if_file_exists: Literal["merge", "overwrite", "raise"] = "raise",
) -> None:
    """Write simulation data to csv file.

    This is a convenience function because ``sinter`` does not expose this functionality. To read
    simulation data use ``sinter.read_stats_from_csv_files``.

    Args:
        filepath: The file to be written to.
        stats: List of simulation results. Each element corresponds to a line in a csv file.
        if_file_exists: How to react if ``filepath`` points to an existing file.
            - raise: Raise a ``TQECError`` if the file exists.
            - overwrite: Effectively delete the file and pretend none exists.
            - merge: Read the file and try to match entries with the simulation data from ``stats``
                by strong id. In case of a match merge the entries.

    """
    filepath = Path(filepath)

    if filepath.exists():
        if if_file_exists == "raise":
            raise TQECError(f"File '{filepath}' already exists.")
        elif if_file_exists == "overwrite":
            # Overwrite happens later automatically.
            pass
        elif if_file_exists == "merge":
            # Writing stats to a file is necessary because sinter does not expose merging via API.
            # We can only indirectly merge by reading in two files.
            in_memory_file = io.StringIO()
            _write_sinter_stats(in_memory_file, stats)
            _ = in_memory_file.seek(0)
            stats = sinter.read_stats_from_csv_files(filepath, in_memory_file)

    with open(filepath, "w") as f:
        _write_sinter_stats(f, stats)


def _write_sinter_stats(file: TextIO, stats: Iterable[sinter.TaskStats]) -> None:
    _ = file.write(sinter.CSV_HEADER + "\n")
    for sample in stats:
        _ = file.write(sample.to_csv_line() + "\n")
