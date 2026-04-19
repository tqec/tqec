"""Read block graphs contained in a lattice surgery (LS) `.bgraph` file."""

import re
from io import StringIO
from pathlib import Path
from typing import Any

from tqec.interop.shared import LoadFromAnywhere
from tqec.utils.exceptions import TQECError


class LoadFromBgraphFile(LoadFromAnywhere):
    """Implement ABC :class:`LoadFromFile` for :filetype:`.bgraph`."""

    def parse(
        self,
        filepath: str | Path | None = None,
        io_str: StringIO | None = None,
        input_in_other_format: Any | None = None,
    ) -> dict[str, Any]:
        """Construct a :class:`.BlockGraph` from a :filetype:`.bgraph`.

        Args:
            filepath (optional): The input `.bgraph` file path.
            io_str (optional): An IO string with the contents of a file (not used in this subclass).
            input_in_other_format (optional): Input in any other format (not used in this subclass).

        Returns:
            parsed_data: The data in the source parsed as a dict representation of a blockgraph.
                `` {
                        name: str,  # The name for the blockgraph.
                        pipe_length,  # The length of the pipes/edges in blockgraph.
                        cubes: {
                            cube_id: {
                                position: tuple[int, int, int],  # The position of the cube.
                                kind: str, # The kind of cube.
                                label: str,  # Optional label to specify ports.
                            }
                        }
                        pipe: {
                            (src_id, tgt_id): {
                                kind: str,  # The kind of pipe.
                            }
                        }
                    }
                ``

        Raises:
            TQECError: If the data cannot be parsed.

        """
        if not filepath or io_str or input_in_other_format:
            raise TQECError("The parsing method is currently only for `.bgraph` files.")

        # Read file
        with open(filepath) as f:
            lines = f.read()
            f.close()

        # Meta
        graph_name_match = re.search(r"(?<=circuit_name; )(.*\b)", lines)
        pipe_length_match = re.search(r"(?<=pipe_length; )(.*\b)", lines)
        graph_name = graph_name_match.group(0) if graph_name_match else "circuit"
        pipe_length = float(pipe_length_match.group(0)) if pipe_length_match else 2.0

        # Find all cubes and pipes in `.bgraph`
        cube_matches = re.finditer(r"(?<=\n)(?:\-*\d*;){3,}.*", lines)
        pipe_matches = re.finditer(r"(?<=\n)(?:\d*;){2}\w{3};", lines)

        # Cubes
        parsed_cubes: dict[int, dict[str, tuple[int, int, int] | str]] = {}
        try:
            for match in cube_matches:
                cube_id, x, y, z, kind, label, _ = match.group(0).strip().split(";")
                parsed_cubes[int(cube_id)] = {
                    "position": (int(x), int(y), int(z)),
                    "kind": kind.upper() if kind.upper() != "OOO" else "P",
                    "label": label,
                }
        except (ValueError, TypeError, IndexError, KeyError):
            raise TQECError("Error parsing cubes from `.bgraph` file.")

        # Pipes
        parsed_pipes: dict[tuple[int, int], dict[str, tuple[int, int, int] | str]] = {}
        try:
            for match in pipe_matches:
                src_id, tgt_id, kind, _ = match.group(0).strip().split(";")
                parsed_pipes[(int(src_id), int(tgt_id))] = {"kind": kind.upper()}
        except (ValueError, TypeError, IndexError, KeyError):
            raise TQECError("Error parsing pipes from `.bgraph` file.")

        # Pack data & return
        return {
            "name": graph_name,
            "pipe_length": pipe_length,
            "cubes": parsed_cubes,
            "pipes": parsed_pipes,
        }
