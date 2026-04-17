"""Read block graphs contained in a lattice surgery (LS) `.bgraph` file."""

import re
from pathlib import Path
from typing import Any

from tqec.computation.block_graph import block_kind_from_str
from tqec.computation.cube import YHalfCube
from tqec.interop.shared import LoadFromFile, int_position_before_scale, offset_y_cube_position
from tqec.utils.exceptions import TQECError
from tqec.utils.position import FloatPosition3D


class LoadFromBgraph(LoadFromFile):
    """Implement ABC :class:`LoadFromFile` for :filetype:`.bgraph`."""

    def parse(self, filepath: str | Path) -> dict[str, Any]:
        """Construct a :class:`.BlockGraph` from a :filetype:`.bgraph`.

        Args:
            filepath: The input `.bgraph` file path.
            graph_name: The name of the block graph. Default is an empty string.
            pipe_length: The length of pipes used by the source LS software.

        Returns:
            parsed_data: The data in the source parsed as a dict representation of a blockgraph.
                `` {
                        name: str,  # The name for the blockgraph
                        cubes: [{
                            position: tuple[int, int, int],  # The position of the target cube.
                            kind: str, # The kind of cube.
                            label: str,  # Optional label to specify ports.
                        }]
                        pipe: [{
                            u: tuple[int, int, int],  # The position of source cube.
                            v: tuple[int, int, int],  # The position of target cube.
                            kind: str,  # The kind of pipe.
                        }]
                    }
                ``

        Raises:
            TQECError: If the data cannot be parsed.

        """
        # Read file
        with open(filepath) as f:
            lines = f.read()
            f.close()

        # Meta
        graph_name = re.search(r"(?<=circuit_name; )(.*\b)", lines).group(0)
        pipe_length = float(re.search(r"(?<=pipe_length; )(.*\b)", lines).group(0))

        # Find all cubes and pipes in `.bgraph`
        cube_matches = re.finditer(r"(?<=\n)(?:\-*\d*;){3,}.*", lines)
        pipe_matches = re.finditer(r"(?<=\n)(?:\d*;){2}\w{3};", lines)

        # Cubes
        parsed_cubes: dict[int, dict[str, tuple[int, int, int] | str]] = {}
        try:
            for match in cube_matches:
                cube_id, x, y, z, kind, label, _ = match.group(0).strip().split(";")
                raw_pos = FloatPosition3D(int(x), int(y), int(z))
                position = None

                if "y" in kind:
                    if isinstance(block_kind_from_str(kind), YHalfCube):
                        position = int_position_before_scale(
                            offset_y_cube_position(raw_pos, pipe_length), pipe_length
                        )
                    else:
                        raise ValueError("Error parsing cubes from `.bgraph` file. Invalid Y kind.")
                else:
                    position = int_position_before_scale(raw_pos, pipe_length)

                if position:
                    parsed_cubes[int(cube_id)] = {
                        "position": position.as_tuple(),
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
                parsed_pipes[(int(src_id), int(tgt_id))] = {
                    "u": parsed_cubes[int(src_id)]["position"],
                    "v": parsed_cubes[int(tgt_id)]["position"],
                    "kind": kind.upper(),
                }
        except (ValueError, TypeError, IndexError, KeyError):
            raise TQECError("Error parsing pipes from `.bgraph` file.")

        # Pack data & return
        return {
            "name": graph_name,
            "cubes": list(parsed_cubes.values()),
            "pipes": list(parsed_pipes.values()),
        }


###################################################################
# QUICK TEST THAT SHOULD BE REMOVED AND EXCHANGED FOR A REAL TEST #
###################################################################
if __name__ == "__main__":

    def write_to_html(filename, html_content):
        """Convert visualised blockgraphs into HTML files."""
        with open(f"{filename}.html", "w") as f:
            f.write(str(html_content))
            f.close()

    # Paths
    graph_name = "cnots"
    EXAMPLE_FOLDER = Path(__file__).parent
    TQEC_FOLDER = EXAMPLE_FOLDER.parent.parent.parent.parent
    ASSETS_FOLDER = TQEC_FOLDER / "assets"
    filepath = ASSETS_FOLDER / f"{graph_name}.bgraph"

    # Create & visualise graph
    graph = LoadFromBgraph().load(filepath)
    write_to_html(graph_name, graph.view_as_html())
