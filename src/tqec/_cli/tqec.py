import argparse
import logging
import sys

from tqec._cli.subcommands.check_dae import CheckDaeTQECSubCommand
from tqec._cli.subcommands.dae2circuits import Dae2CircuitsTQECSubCommand
from tqec._cli.subcommands.dae2observables import Dae2ObservablesTQECSubCommand
from tqec._cli.subcommands.run_example import RunExampleTQECSubCommand
from tqec._cli.subcommands.viz import VisualisationTQECSubCommand

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tqec",
        description="The main tqec command-line tool.",
    )
    parser.add_argument(
        "--log-level",
        help=(
            "Logging level for the tqec CLI and library. INFO shows the steps of a "
            "subcommand, DEBUG also shows details such as the compilation steps. "
            "Default: WARNING."
        ),
        type=str.upper,
        choices=LOG_LEVELS,
        default="WARNING",
    )
    subparser = parser.add_subparsers(title="subcommands")

    Dae2ObservablesTQECSubCommand.add_subcommand(subparser)
    CheckDaeTQECSubCommand.add_subcommand(subparser)
    Dae2CircuitsTQECSubCommand.add_subcommand(subparser)
    RunExampleTQECSubCommand.add_subcommand(subparser)
    VisualisationTQECSubCommand.add_subcommand(subparser)
    return parser


def main() -> None:
    """Entry point of TQEC CLI."""
    parser = _build_parser()
    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])
    # basicConfig adds a handler only if the root logger has none; the level is
    # set separately so that --log-level applies either way.
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger().setLevel(args.log_level)
    args.func(args)
