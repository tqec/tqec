from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import sinter
from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand


class PlotSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "plot",
            description=(
                "Plot the results of an existing CSV file from a simulation. "
                "Useful to tweak the limits of the plots."
            ),
        )
        parser.add_argument(
            "-d",
            "--directory",
            help="Directory for relative CSV paths and generated plots.",
            type=Path,
            default="simulations",
        )
        parser.add_argument(
            "csv_file",
            help="Simulation CSV file, relative to --directory or an absolute path.",
            type=Path,
        )
        parser.add_argument(
            "--xlim",
            nargs=2,
            type=float,
            metavar=("MIN", "MAX"),
            default=(1e-4, 0.0125),
            help="Physical error rate limits (0 < MIN < MAX).",
        )
        parser.add_argument(
            "--ylim",
            nargs=2,
            type=float,
            metavar=("MIN", "MAX"),
            default=(1.25e-9, 1.25),
            help="Logical error rate limits (0 < MIN < MAX).",
        )
        parser.set_defaults(func=PlotSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        # Parse args
        logging.info("Parsing arguments.")
        for option in ("xlim", "ylim"):
            lower, upper = getattr(args, option)
            if not 0 < lower < upper < float("inf"):
                raise ValueError(f"--{option} requires finite limits with 0 < MIN < MAX.")
        directory: Path = args.directory.resolve()
        csv_path: Path = (directory / args.csv_file).resolve()
        output_path = directory / f"{csv_path.stem}.png"

        print(f"Working on CSV : {csv_path.name}")

        stats = sinter.stats_from_csv_files(csv_path)
        print(f"Stats : {len(stats)}")

        fig, ax = plt.subplots()
        sinter.plot_error_rate(
            ax=ax,
            stats=stats,
            x_func=lambda stat: stat.json_metadata["p"],
            group_func=lambda stat: stat.json_metadata["d"],
        )
        # plot_observable_as_inset(ax, zx_graph, correlation_surfaces[i])
        ax.grid(axis="both")
        ax.set_xlabel("Physical Error Rate")
        ax.set_xlim(*args.xlim)
        ax.set_ylabel("Logical Error Rate")
        ax.set_ylim(*args.ylim)
        ax.legend()
        ax.loglog()
        ax.set_title(f"{csv_path.stem}")
        directory.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)

        print(f"Saved {output_path}")
