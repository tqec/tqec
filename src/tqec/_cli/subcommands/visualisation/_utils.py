import shutil
import subprocess
from pathlib import Path


def has_program(name: str) -> bool:
    return shutil.which(name) is not None


def generate_animation(
    out_file: Path,
    framerate: int,
    image_directory: Path,
    image_glob_pattern: str = "*.svg",
    overwrite: bool = True,
) -> None:
    overwrite_str = "-y" if overwrite else "-n"
    command = (
        f"ffmpeg {out_file} {overwrite_str} -framerate {framerate} -pattern_type "
        f"glob -i {image_directory}/{image_glob_pattern} -vf scale=1024:-1 -c:v "
        "libx264 -vf format=yuv420p -vf pad=ceil(iw/2)*2:ceil(ih/2)*2 -filter_complex "
        "[0]split=2[bg][fg];[bg]drawbox=c=white@1:t=fill[bg];[bg][fg]overlay=format=auto"
    )
    result = subprocess.run(command.split(), capture_output=True)
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
