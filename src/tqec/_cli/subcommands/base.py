from __future__ import annotations

import argparse
from abc import ABC, abstractmethod


class TQECSubCommand(ABC):
    """Interface that should be implemented by subcommands of the tqec CLI."""

    @staticmethod
    @abstractmethod
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        """Create a CLI for the subcommand using the provided ``main_parser``."""
        pass

    @staticmethod
    @abstractmethod
    def execute(args: argparse.Namespace) -> None:
        """Execute the subcommand from the provided parsed arguments."""
        pass
