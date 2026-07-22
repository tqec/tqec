from __future__ import annotations

import argparse
from pathlib import Path

from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec.interop.batch import batch_dae_to_bgraph, split_dae_batch


class Dae2BatchTQECSubCommand(TQECSubCommand):
    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "dae2batch",
            description="Split a .dae file holding several disjoint structures into one "
            "file per structure, named <stem>_batch<NN>.",
        )
        parser.add_argument("dae_file", help="The .dae file to split.", type=Path)
        parser.add_argument(
            "-o",
            "--out-dir",
            help="Directory the component files are written to. Defaults to a "
            "'<stem>_batch' directory next to the input file.",
            type=Path,
            default=None,
        )
        parser.add_argument(
            "--bgraph",
            help="Also convert each component to a .bgraph file.",
            action="store_true",
        )
        parser.add_argument(
            "--clean",
            help="Remove pre-existing output files from the output directory first.",
            action="store_true",
        )
        parser.set_defaults(func=Dae2BatchTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        dae_path: Path = args.dae_file.resolve()
        out_dir: Path = args.out_dir or dae_path.parent / f"{dae_path.stem}_batch"

        components = split_dae_batch(dae_path, out_dir, clean=args.clean)
        print(f"Wrote {len(components)} component .dae files to {out_dir}")

        if not args.bgraph:
            return

        written, failures = batch_dae_to_bgraph(components, out_dir, clean=args.clean)
        print(f"Converted {len(written)}/{len(components)} components to .bgraph")
        for failure in failures:
            print(f"  failed: {failure}")
