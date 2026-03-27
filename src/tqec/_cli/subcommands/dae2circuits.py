from __future__ import annotations

import argparse
from pathlib import Path

from tqecd.construction import annotate_detectors_automatically
from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec._cli.subcommands.dae2observables import save_correlation_surfaces_to
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION
from tqec.computation.block_graph import BlockGraph


class Dae2CircuitsTQECSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "dae2circuits",
            description=(
                "Convert a .dae file representing a logical computation "
                "into concrete stim circuits."
            ),
        )
        parser.add_argument(
            "dae_file",
            help="A valid .dae file representing a computation.",
            type=Path,
        )
        parser.add_argument(
            "--out-dir",
            help="Directory to save the generated stim circuits.",
            type=Path,
            required=True,
        )
        parser.add_argument(
            "-k",
            help="The scale factors applied to the circuits.",
            nargs="+",
            type=int,
            required=True,
        )
        parser.add_argument(
            "--obs-include",
            help=(
                "The observable indices to be included in the circuits. "
                "If not provided, all potential observables will be included."
            ),
            nargs="*",
            type=int,
            default=None,
        )
        parser.add_argument(
            "--add-detectors",
            help="Whether to add detectors to the circuits.",
            action="store_true",
        )
        # TODO: add noise models
        parser.set_defaults(func=Dae2CircuitsTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        dae_absolute_path: Path = args.dae_file.resolve()
        out_dir: Path = args.out_dir.resolve()
        if not out_dir.exists():
            out_dir.mkdir(parents=True)

        # Construct the block graph from the given .dae file
        block_graph = BlockGraph.from_dae_file(
            dae_absolute_path, graph_name=str(dae_absolute_path.name)
        )

        # Convert to ZX graph and find observables
        zx_graph = block_graph.to_zx_graph()
        # Save the plotted observables to a subdirectory
        observable_out_dir = out_dir / "observables"
        observable_out_dir.mkdir(exist_ok=True)
        correlation_surfaces = block_graph.find_correlation_surfaces()
        obs_indices: list[int] | None = args.obs_include
        # Fix: distinguish between not-provided (None -> include all) and explicitly
        # provided empty list ([] -> include none).
        if obs_indices is None:
            obs_indices = list(range(len(correlation_surfaces)))
        if len(obs_indices) == 0:
            raise ValueError("No observables selected. Provide --obs-include or omit it to include all.")
        if max(obs_indices) >= len(correlation_surfaces):
            raise ValueError(
                f"Found {len(correlation_surfaces)} observables, but requested "
                f"indices up to {max(obs_indices)}."
            )

        save_correlation_surfaces_to(
            zx_graph,
            observable_out_dir,
            [correlation_surfaces[i] for i in obs_indices],
        )

        # Compile the block graph and generate stim circuits
        circuits_out_dir = out_dir / "circuits"
        circuits_out_dir.mkdir(exist_ok=True)
        compiled_graph = compile_block_graph(
            block_graph,
            FIXED_BULK_CONVENTION,
            observables=[correlation_surfaces[i] for i in obs_indices],
        )
        ks: list[int] = args.k
        add_detectors: bool = args.add_detectors
        for k in ks:
            circuit = compiled_graph.generate_stim_circuit(k)
            if add_detectors:
                circuit = annotate_detectors_automatically(circuit)
            out_file = circuits_out_dir / f"{k}.stim"  # Fix: avoid filenames like 'k=3.stim'.
            circuit.to_file(out_file)
            print(f"Write circuit to {out_file}.")  # Fix: print full file path for debugging.
