from __future__ import annotations

import argparse

from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec._cli.subcommands.visualisation.anm.circ import (
    VisualisationAnmCircuitTQECSubCommand,
)


class VisualisationAnmTQECSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "anm", description="Generating animations."
        )
        subparser = parser.add_subparsers()
        VisualisationAnmCircuitTQECSubCommand.add_subcommand(subparser)
        parser.set_defaults(func=VisualisationAnmTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        print(args)
