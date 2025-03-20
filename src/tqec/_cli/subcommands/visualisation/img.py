from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import stim
from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand


class VisualisationImgTQECSubCommand(TQECSubCommand):
    _STYLE_TO_STIM_DIAGRAM: Final[dict[str, str]] = {
        "circ": "timeslice-svg",
        "det": "detslice-svg",
        "circdet": "detslice-with-ops-svg",
    }

    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "img", description="Generating images representing quantum circuits."
        )
        parser.add_argument(
            "-i",
            "--in_file",
            type=Path,
            required=True,
            help="Quantum circuit in Stim format that should be represented as an image.",
        )
        parser.add_argument(
            "-o",
            "--out_file",
            type=Path,
            required=True,
            help=(
                "Output filename that will be used to write the resulting "
                "image. Should have the '.svg' extension."
            ),
        )
        parser.add_argument(
            "-t",
            "--ticks",
            default="ALL",
            help=(
                "A colon separated pair a:b where a < b representing the TICKS "
                "to include in the animation. Defaults to ALL, meaning all TICKS."
            ),
        )
        parser.add_argument(
            "--with_noise",
            action="store_true",
            help="If provided, noise instructions are included in the visualisation.",
        )
        parser.add_argument(
            "--style",
            choices=VisualisationImgTQECSubCommand._STYLE_TO_STIM_DIAGRAM.keys(),
            default="circ",
            help="Type of diagram to generate for the image.",
        )
        parser.set_defaults(func=VisualisationImgTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        circuit = stim.Circuit.from_file(args.in_file)
        if not args.with_noise:
            circuit = circuit.without_noise()
        start_tick, end_tick = 0, circuit.num_ticks + 1
        if args.ticks != "ALL":
            start_tick, end_tick = tuple(int(s) for s in args.ticks.split(":"))
        style = VisualisationImgTQECSubCommand._STYLE_TO_STIM_DIAGRAM[args.style]
        with open(args.out_file, "w") as f:
            f.write(str(circuit.diagram(style, tick=range(start_tick, end_tick))))
