from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Final

import stim
from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec._cli.subcommands.visualisation._utils import (
    generate_animation,
    has_program,
)
from tqec.utils.exceptions import TQECException


class VisualisationAnmTQECSubCommand(TQECSubCommand):
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
            "anm", description="Generating animations."
        )
        parser.add_argument(
            "-i",
            "--in_file",
            type=Path,
            required=True,
            help="Quantum circuit in Stim format that should be animated.",
        )
        parser.add_argument(
            "-o",
            "--out_file",
            type=Path,
            required=True,
            help="Output filename that will be used to write the animation.",
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
            "-f",
            "--framerate",
            type=int,
            default=5,
            help="Number of TICKS per seconds in the returned animation.",
        )
        parser.add_argument(
            "--with_noise",
            action="store_true",
            help="If provided, noise instructions are included in the visualisation.",
        )
        parser.add_argument(
            "--style",
            choices=VisualisationAnmTQECSubCommand._STYLE_TO_STIM_DIAGRAM.keys(),
            default="circ",
            help="Type of diagram to generate for the animation.",
        )
        parser.set_defaults(func=VisualisationAnmTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        if not has_program("ffmpeg"):
            raise TQECException(
                "Generating animations with 'tqec viz anm' requires a "
                "working installation of ffmpeg. Could not find the ffmpeg "
                "executable on your path."
            )
        circuit = stim.Circuit.from_file(args.in_file)
        if not args.with_noise:
            circuit = circuit.without_noise()
        start_tick, end_tick = 0, circuit.num_ticks + 1
        if args.ticks != "ALL":
            start_tick, end_tick = tuple(int(s) for s in args.ticks.split(":"))
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Step one, generate the individual TICKs
            print("Generating individual images...")
            style = VisualisationAnmTQECSubCommand._STYLE_TO_STIM_DIAGRAM[args.style]
            for t in range(start_tick, end_tick):
                with open(f"{tmpdirname}/{t}.svg", "w") as f:
                    f.write(str(circuit.diagram(style, tick=t)))
            # Step two, generate a video with ffmpeg
            print("Generating animation (this may take some time)...")
            generate_animation(args.out_file, args.framerate, Path(tmpdirname))
