from __future__ import annotations

import argparse
import logging
from multiprocessing import cpu_count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import sinter
from typing_extensions import override

from tqec import BlockGraph
from tqec._cli.subcommands.base import TQECSubCommand
from tqec._cli.subcommands.dae2observables import save_correlation_surfaces_to
from tqec.compile.convention import ALL_CONVENTIONS
from tqec.simulation import plot_observable_as_inset
from tqec.simulation.simulation import start_simulation_using_sinter
from tqec.utils.noise_model import NoiseModel


class SimulateSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "simulate",
            description=("Performs a complete simulation of a given BlockGraph computation."),
        )
        parser.add_argument(
            "-c",
            "--convention",
            help="Convention to use.",
            choices=ALL_CONVENTIONS.keys(),
            default="fixed_bulk",
        )
        parser.add_argument(
            "-d",
            "--output-directory",
            help="Directory where all the generated files will be saved.",
            type=Path,
            default="simulations",
        )
        parser.add_argument(
            "-e",
            "--errors",
            help="The maximum number of errors allowed.",
            type=float,
            default=5e3,
        )
        parser.add_argument(
            "-k",
            help="The scale factors applied to the circuits (distance is 2*k+1).",
            nargs="+",
            type=int,
            default=[1, 2, 3],
        )
        parser.add_argument(
            "-o",
            "--observables",
            help=(
                "The indices of the observables to be included in the circuits. "
                "If not provided, all potential observables will be included."
            ),
            nargs="*",
            type=int,
        )
        parser.add_argument(
            "-p",
            help="The noise levels applied to the simulation (aka Physical Error Rate).",
            nargs="+",
            type=float,
            default=list(np.logspace(-4, -1, 10)),
        )
        parser.add_argument(
            "-s",
            "--shots",
            help="The number of shots to perform.",
            type=float,
            default=1e6,
        )
        parser.add_argument(
            "dae_file",
            help="A valid .DAE file representing a computation.",
            type=Path,
        )
        parser.set_defaults(func=SimulateSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        # Parse args
        logging.info("Parsing arguments.")
        output: Path = args.output_directory.resolve()
        label: str = args.dae_file.stem
        ks: list[int] = args.k
        ps: list[float] = args.p

        # Set up the output directories
        if not output.exists():
            output.mkdir(parents=True)

        logging.info("Generating block graph and zx graph.")
        block_graph = BlockGraph.from_dae_file(args.dae_file)
        zx_graph = block_graph.to_zx_graph()

        # Save all observables as ONGs. Useful if using plot_results subcommand.
        correlation_surfaces = block_graph.find_correlation_surfaces()
        observables: list[int] = args.observables or list(range(len(correlation_surfaces)))
        if max(observables) >= len(correlation_surfaces):
            raise ValueError(
                f"Found {len(correlation_surfaces)} observables,"
                + f"but requested indices up to {max(observables)}."
            )
        convention = ALL_CONVENTIONS[args.convention]

        save_correlation_surfaces_to(
            zx_graph, output, [correlation_surfaces[i] for i in observables]
        )

        logging.info("Start the simulation, this might take some time.")
        stats = start_simulation_using_sinter(
            block_graph,
            ks,
            ps,
            NoiseModel.uniform_depolarizing,
            manhattan_radius=2,
            convention=convention,
            observables=[correlation_surfaces[i] for i in observables],
            num_workers=cpu_count(),
            max_shots=int(args.shots),
            max_errors=int(args.errors),
            decoders=["pymatching"],
            print_progress=True,
        )
        logging.info("Simulation finished.")

        logging.info("Write generated files.")
        for i, stat in enumerate(stats):
            with open(
                f"{output}/{label}_{convention}_results_observable_{i}.csv",
                "w+",
                encoding="utf-8",
            ) as stats_file:
                stats_file.write(sinter.CSV_HEADER + "\n")
                for sub_stat in stat:
                    stats_file.write(sub_stat.to_csv_line() + "\n")

            fig, ax = plt.subplots()
            sinter.plot_error_rate(
                ax=ax,
                stats=stat,
                x_func=lambda stat: stat.json_metadata["p"],
                group_func=lambda stat: stat.json_metadata["d"],
            )
            plot_observable_as_inset(ax, zx_graph, correlation_surfaces[observables[i]])
            ax.grid(axis="both")
            ax.set_xlabel("Physical Error Rate")
            ax.set_xlim(1e-4, 0.0125)
            ax.set_ylabel("Logical Error Rate")
            ax.set_ylim(1.25e-9, 1.25)
            ax.legend()
            ax.loglog()
            ax.set_title(f"{label} [{convention}]")
            fig.savefig(f"{output}/{label}_{convention}_results_observable_{i}.png")
