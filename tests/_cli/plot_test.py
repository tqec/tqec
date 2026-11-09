import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
import sinter

from tqec._cli.subcommands.plot import PlotSubCommand


def parse_args(arguments: list[str]) -> argparse.Namespace:
    """Parse arguments through the plot subcommand's public parser."""
    parser = argparse.ArgumentParser()
    PlotSubCommand.add_subcommand(parser.add_subparsers())
    return parser.parse_args(["plot", *arguments])


@pytest.mark.parametrize("absolute_csv", [False, True])
@pytest.mark.parametrize("custom_limits", [False, True])
def test_plot_directory_and_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, absolute_csv: bool, custom_limits: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "simulation"
    directory.mkdir()
    csv_path = (tmp_path if absolute_csv else directory) / "results.csv"
    stat = sinter.TaskStats(
        strong_id="test",
        decoder="pymatching",
        json_metadata={"p": 0.001, "d": 3},
        shots=1000,
        errors=10,
    )
    csv_path.write_text(sinter.CSV_HEADER + "\n" + stat.to_csv_line() + "\n")
    arguments = ["-d", str(directory), str(csv_path) if absolute_csv else csv_path.name]
    if custom_limits:
        arguments.extend(["--xlim", "1e-5", "0.02", "--ylim", "1e-7", "1"])
    args = parse_args(arguments)
    try:
        args.func(args)
        ax = plt.gcf().axes[0]
        assert ax.get_xlim() == pytest.approx((1e-5, 0.02) if custom_limits else (1e-4, 0.0125))
        assert ax.get_ylim() == pytest.approx((1e-7, 1) if custom_limits else (1.25e-9, 1.25))
        assert (directory / "results.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert not (tmp_path / "results.png").exists()
    finally:
        plt.close("all")


@pytest.mark.parametrize("option", ["--xlim", "--ylim"])
@pytest.mark.parametrize("limits", [("0", "1"), ("2", "1"), ("1", "1"), ("nan", "1"), ("1", "inf")])
def test_plot_invalid_limits(option: str, limits: tuple[str, str]) -> None:
    args = parse_args(["results.csv", option, *limits])
    with pytest.raises(ValueError, match=f"{option} requires finite limits"):
        args.func(args)
