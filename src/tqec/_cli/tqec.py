import argparse
import sys

from tqec._cli.subcommands.check_dae import CheckDaeTQECSubCommand
from tqec._cli.subcommands.dae2circuits import Dae2CircuitsTQECSubCommand
from tqec._cli.subcommands.dae2observables import Dae2ObservablesTQECSubCommand
from tqec._cli.subcommands.run_example import RunExampleTQECSubCommand
from tqec._cli.subcommands.viz import VisualisationTQECSubCommand


def main() -> None:
    """Entry point of TQEC CLI."""
    parser = argparse.ArgumentParser(
        prog="tqec",
        description="The main tqec command-line tool.",
    )
    subparser = parser.add_subparsers(title="subcommands")

    Dae2ObservablesTQECSubCommand.add_subcommand(subparser)
    CheckDaeTQECSubCommand.add_subcommand(subparser)
    Dae2CircuitsTQECSubCommand.add_subcommand(subparser)
    RunExampleTQECSubCommand.add_subcommand(subparser)
    VisualisationTQECSubCommand.add_subcommand(subparser)

    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])
    args.func(args)
