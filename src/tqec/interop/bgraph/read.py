"""Read block graphs contained in a lattice surgery (LS) `.bgraph` file."""

import re
from io import StringIO
from pathlib import Path
from typing import Any

from tqec.computation.block_graph import BlockGraph
from tqec.interop.shared import LoadFromAnywhere
from tqec.utils.exceptions import TQECError


class LoadFromBgraph(LoadFromAnywhere):
    """Implement ABC :class:`LoadFromFile` for :filetype:`.bgraph`."""

    def parse(
        self,
        raw_str: str | None = None,
        filepath: str | Path | None = None,
        io_str: StringIO | None = None,
        input_in_other_format: Any | None = None,
    ) -> dict[str, Any]:
        """Construct a :class:`.BlockGraph` from a :filetype:`.bgraph`.

        Args:
            raw_str: A string containing a blockgraph in `.bgraph` format.
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
        # Validate input types
        if io_str or input_in_other_format:
            raise TQECError("The parsing method is currently only for `.bgraph` files.")

        if not raw_str and not filepath:
            raise TQECError("LoadFromBgraph requires a `.bgraph` string or filepath.")

        # Read file
        bgraph_str: str = raw_str if raw_str else ""
        if filepath:
            with open(filepath) as f:
                bgraph_str = f.read()
                f.close()

        if bgraph_str == "":
            raise TQECError("LoadFromBgraph failed. Empty bgraph string.")

        # Meta
        graph_name_match = re.search(r"(?<=circuit_name; )(.*\b)", bgraph_str)
        pipe_length_match = re.search(r"(?<=pipe_length; )(.*\b)", bgraph_str)
        graph_name = graph_name_match.group(0) if graph_name_match else "circuit"
        pipe_length = float(pipe_length_match.group(0)) if pipe_length_match else 0.0

        # Find all cubes and pipes in `.bgraph`
        cube_matches = re.finditer(r"(?<=\n)(?:\-*\d*;){3,}.*", bgraph_str)
        pipe_matches = re.finditer(r"(?<=\n)(?:\d*;){2}\w{3};", bgraph_str)

        # Cubes
        parsed_cubes: dict[int, dict[str, tuple[int, int, int] | str]] = {}
        try:
            for match in cube_matches:
                cube_id, x, y, z, kind, label, _ = match.group(0).strip().split(";")
                parsed_cubes[int(cube_id)] = {
                    "position": (int(x), int(y), int(z)),
                    "kind": kind.upper(),
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


# Direct wrapper
def read_block_graph_from_bgraph(
    bgraph_str: str | None = None,
    filepath: str | Path | None = None,
    graph_name: str | None = None,
) -> BlockGraph:
    """Read a :filetype:`.bgraph` and construct a :class:`.BlockGraph` from it.

    Args:
        bgraph_str: A string containing a blockgraph in `.bgraph` format.
        filepath: The input `.bgraph` file path.
        graph_name: The name of the block graph, in case it is not given explicitly in metadata.

    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        TQECError: If the :filetype:`.bgraph` cannot be parsed and converted to a block graph.

    """
    return LoadFromBgraph().load(
        raw_str=bgraph_str, filepath=filepath, override_graph_name=graph_name
    )
