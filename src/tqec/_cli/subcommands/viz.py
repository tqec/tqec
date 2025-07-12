from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final

import stim
from typing_extensions import override

from tqec._cli.subcommands.base import TQECSubCommand
from tqec.utils.exceptions import TQECError


def has_program(name: str) -> bool:
    """Check if the provided ``name`` corresponds to a usable executable on the host system."""
    return shutil.which(name) is not None


def generate_animation(
    out_file: Path,
    framerate: int,
    image_directory: Path,
    image_glob_pattern: str = "*.svg",
    overwrite: bool = True,
) -> None:
    """Generate an animation from a directory containing images.

    Args:
        out_file: filepath to save the animation to.
        framerate: how many images per seconds should be displayed in the animated video.
        image_directory: a directory containing images following the provided
            ``image_glob_pattern``. Images should be named appropriately to be sorted.
        image_glob_pattern: file pattern used to get the list of all the images that should be
            in the saved video.
        overwrite: if ``True`` and ``out_file`` already exists, it will be overwritten. Else, the
            file will not be updated.

    Raises:
        TQECError: if ``ffmpeg`` is not available in the host system.

    """
    if not has_program("ffmpeg"):
        raise TQECError(
            "ffmpeg is needed to generate an animation, but could not find it. "
            "Make sure you have ffmpeg installed and that it is accessible."
        )
    overwrite_str = "-y" if overwrite else "-n"
    command = (
        f"ffmpeg {out_file} {overwrite_str} -framerate {framerate} -pattern_type "
        f"glob -i {image_directory}/{image_glob_pattern} -vf scale=1024:-1 -c:v "
        "libx264 -vf format=yuv420p -vf pad=ceil(iw/2)*2:ceil(ih/2)*2 -filter_complex "
        "[0]split=2[bg][fg];[bg]drawbox=c=white@1:t=fill[bg];[bg][fg]overlay=format=auto"
    )
    result = subprocess.run(command.split(), capture_output=True, check=False)
    # Print the path of the generated video on success.
    if result.returncode == 0:
        print(f"Video successfully generated at '{out_file}'.")
    else:
        linesep = "=" * 40
        print(f"Error when generating the video. Returned {result.returncode}.")
        print("Full stdout:")
        print(linesep)
        print(result.stdout.decode("utf-8"))
        print(linesep)
        print("Full stderr:")
        print(linesep)
        print(result.stderr.decode("utf-8"))
        print(linesep)


class VisualisationTQECSubCommand(TQECSubCommand):
    _STYLE_TO_STIM_DIAGRAM: Final[dict[str, str]] = {
        "timeslice": "timeslice-svg",
        "detslice": "detslice-svg",
        "detslice-with-ops": "detslice-with-ops-svg",
    }

    @staticmethod
    @override
    def add_subcommand(
        main_parser: argparse._SubParsersAction[argparse.ArgumentParser],
    ) -> None:
        parser: argparse.ArgumentParser = main_parser.add_parser(
            "viz", description="Generating images and videos from quantum circuits."
        )
        parser.add_argument(
            "-i",
            "--in_file",
            type=Path,
            required=True,
            help="Quantum circuit in Stim format that should be visualised.",
        )
        parser.add_argument(
            "-o",
            "--out_file",
            type=Path,
            required=True,
            help="Output filename that will be used to write the visualisation.",
        )
        parser.add_argument(
            "-t",
            "--ticks",
            default="ALL",
            help=(
                "A colon separated pair a:b where a < b representing the TICKS "
                "to include in the visualisation. Defaults to ALL, meaning all "
                "TICKS."
            ),
        )
        parser.add_argument(
            "--with_noise",
            action="store_true",
            help="If provided, noise instructions are included in the visualisation.",
        )
        parser.add_argument(
            "--style",
            choices=VisualisationTQECSubCommand._STYLE_TO_STIM_DIAGRAM.keys(),
            default="circ",
            help="Type of diagram to generate for the visualisation.",
        )
        parser.add_argument(
            "--anim",
            action="store_true",
            help=(
                "If provided, an animation (video) is generated. Else, an "
                "image containing the needed TICKs is generated."
            ),
        )
        parser.add_argument(
            "-f",
            "--framerate",
            type=int,
            default=5,
            help=(
                "Number of TICKS per seconds in the returned animation. Only "
                "has effect when '--anim' is provided."
            ),
        )
        parser.set_defaults(func=VisualisationTQECSubCommand.execute)

    @staticmethod
    @override
    def execute(args: argparse.Namespace) -> None:
        # Getting the quantum circuit
        circuit = stim.Circuit.from_file(args.in_file)
        if not args.with_noise:
            circuit = circuit.without_noise()
        # Computing the TICKs
        start_tick, end_tick = 0, circuit.num_ticks + 1
        if args.ticks != "ALL":
            start_tick, end_tick = tuple(int(s) for s in args.ticks.split(":"))
        # Getting the diagram style
        style = VisualisationTQECSubCommand._STYLE_TO_STIM_DIAGRAM[args.style]

        if args.anim:
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Step one, generate the individual TICKs
                print("Generating individual images...")
                for t in range(start_tick, end_tick):
                    with open(f"{tmpdirname}/{t:0>4}.svg", "w") as f:
                        f.write(str(circuit.diagram(style, tick=t)))
                # Step two, generate a video with ffmpeg
                print("Generating animation (this may take some time)...")
                generate_animation(args.out_file, args.framerate, Path(tmpdirname))
        else:
            with open(args.out_file, "w") as f:
                f.write(str(circuit.diagram(style, tick=range(start_tick, end_tick))))
