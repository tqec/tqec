from __future__ import annotations

import argparse

from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec._cli.subcommands.visualisation.anm.root import VisualisationAnmTQECSubCommand


class VisualisationTQECSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "viz", description="Visualisation utilities for tqec."
        )
        subparser = parser.add_subparsers()
        VisualisationAnmTQECSubCommand.add_subcommand(subparser)
        parser.set_defaults(func=VisualisationTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        print(args)
