from __future__ import annotations

import argparse
from pathlib import Path

from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec.computation.block_graph import BlockGraph


class CheckDaeTQECSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "check_dae",
            description="Takes a .dae file in and check that it is correctly "
            "recognized by the tqec library.",
        )
        parser.add_argument("dae_file", help="The .dae file to check.", type=Path)
        parser.set_defaults(func=CheckDaeTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        dae_absolute_path: Path = args.dae_file.resolve()
        try:
            BlockGraph.from_dae_file(dae_absolute_path, graph_name=str(dae_absolute_path))
        except Exception as e:
            print("Failed to load the .dae file into a BlockGraph with the following error:")
            print(e)
        else:
            print("No issue found, the provided .dae file seems valid.")
