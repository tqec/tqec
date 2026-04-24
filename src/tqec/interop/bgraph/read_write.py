"""Read block graphs contained in a lattice surgery (LS) :filetype:`.bgraph` (BGRAPH) file."""

import re
from pathlib import Path

from tqec.computation.block_graph import BlockGraph, block_kind_from_str
from tqec.computation.cube import YHalfCube
from tqec.interop.shared import int_position_before_scale, offset_y_cube_position, scale_position
from tqec.utils.exceptions import TQECError
from tqec.utils.position import FloatPosition3D, Position3D


######################
# PRIMARY READ/WRITE #
######################
def load_bgraph(bgraph_str_or_path: str | Path, graph_name: str = "") -> BlockGraph:
    """Construct a :class:`.BlockGraph` from a :filetype:`.bgraph`.

    Args:
        bgraph_str_or_path: Path to input file or input string.
        graph_name (optional): Name to give the blockgraph (overrides name in BGRAPH metadata).

    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        TQECError: If the data cannot be parsed.

    """
    # Ducky McDucky parsing
    bgraph_str = _duck_parse_bgraph(bgraph_str_or_path)

    # Unpack information in BGRAPH string
    pipe_length, graph_name, cube_lines, pipe_lines = _unpack_bgraph_str(
        bgraph_str, graph_name=graph_name
    )

    # Create blockgraph
    block_graph = BlockGraph(graph_name)

    # Add cubes
    parsed_cubes: dict[str, dict[str, Position3D]] = {}
    try:
        for line in cube_lines:
            # Break match into components
            cube_id, x, y, z, kind, label, _ = line.strip().split(";")

            # Reposition cube given kind and pipe_length
            if "Y" in kind.upper():
                if kind.upper() in ["Y", "YI", "YM"]:
                    kind = "Y"
                    if isinstance(block_kind_from_str(kind), YHalfCube):
                        position = int_position_before_scale(
                            offset_y_cube_position(
                                FloatPosition3D(*(int(x), int(y), int(z))), pipe_length
                            ),
                            pipe_length,
                        )
                else:
                    raise TQECError("Error repositioning parsed data: Invalid Y kind.")
            else:
                kind = "P" if kind.upper() == "OOO" else kind.upper()
                position = int_position_before_scale(
                    FloatPosition3D(*(int(x), int(y), int(z))), pipe_length
                )

            # Store repositioned cube to facilitate pipe management later on
            parsed_cubes[cube_id] = {"position": position}

            # Add cube to blockgraph
            block_graph.add_cube(position=position, kind=kind, label=label)
    except Exception as e:
        raise TQECError("Error parsing cubes from BGRAPH file.") from e

    # Add pipes
    try:
        for line in pipe_lines:
            # Break match into components
            src_id, tgt_id, kind, _ = line.strip().split(";")

            # Add pipe to blockgraph using (re)positioned source and target cubes
            block_graph.add_pipe(
                pos1=parsed_cubes[src_id]["position"],
                pos2=parsed_cubes[tgt_id]["position"],
                kind=kind.upper(),
            )
    except Exception as e:
        raise TQECError("Error parsing pipes from BGRAPH file.") from e

    # Pack data & return
    return block_graph


def write_bgraph(
    block_graph: BlockGraph,
    filepath: str | Path,
    pipe_length: float = 0.0,
    graph_name: str = "circuit",
    save_to_file: bool = True,
) -> str:
    """Write a :filetype:`.bgraph` from a :class:`.BlockGraph`.

    Args:
        block_graph: The blockgraph to be written into a BGRAPH file.
        filepath: The output file path or file-like object that supports binary write.
        pipe_length (optional): The length of pipes to use for distancing cubes out.
        graph_name (optional): Name to give the BGRAPH file and add to BGRAPH metadata.
        save_to_file (optional): Flag to trigger file writing (BGRAPH is always returned as string).

    Returns:
        bgraph_str: The blockgraph as a string using the BGRAPH format.

    Raises:
        TQECError: If the BGRAPH cannot be returned or written into file.

    """
    # Initialise lines array
    bgraph_lines = ["BLOCKGRAPH 0.1.0;\n"]

    # Write metadata into lines array
    bgraph_lines.append("\nMETADATA: attr_name; value;\n")
    bgraph_lines.append("source; TQEC.\n")
    bgraph_lines.append(f"pipe_length; {pipe_length};\n")
    bgraph_lines.append(f"circuit_name; {graph_name};\n")

    # Write cubes into lines array
    bgraph_lines.append("\nCUBES: index;x;y;z;kind;label;\n")
    for cube in block_graph.cubes:
        scaled_position = scale_position(cube.position, pipe_length=pipe_length)
        if cube.is_y_cube and block_graph.has_pipe_between(
            cube.position, cube.position.shift_by(dz=1)
        ):
            scaled_position = scaled_position.shift_by(dz=0.5)
        cube_id = str(cube).replace(",", "")
        x, y, z = [int(i) for i in scaled_position.as_array()]
        bgraph_lines.append(f"{cube_id};{x};{y};{z};{cube.kind};{cube.label};\n")

    # Write pipes into lines array
    bgraph_lines.append("\nPIPES: src;tgt;kind;\n")
    for pipe in block_graph.pipes:
        u = str(pipe.u).replace(",", "")
        v = str(pipe.v).replace(",", "")
        bgraph_lines.append(f"{u};{v};{pipe.kind};\n")

    if save_to_file:
        _save_bgraph_to_file(filepath, bgraph_lines)

    return "".join(bgraph_lines)


#######
# AUX #
#######
def _duck_parse_bgraph(bgraph_str_or_path: str | Path) -> str:
    """Parse BGRAPH string as appropriate depending on incoming object.

    Args:
        bgraph_str_or_path: Path to input file or input given as a regular string.

    Return:
        bgraph_str: The input in the final string format needed by the parser.

    Raises:
        TQECError: If the string is not parsed or the parsed string is empty.

    """
    # Reject if input string remains empty
    if bgraph_str_or_path == "":
        raise TQECError("Empty BGRAPH string or filepath.")

    # Looks like a regular string with BGRAPH syntax
    bgraph_str = ""
    if (
        not isinstance(bgraph_str_or_path, Path)
        and bgraph_str_or_path.startswith("BLOCKGRAPH ")
        and ".bgraph" not in bgraph_str_or_path
    ):
        bgraph_str = bgraph_str_or_path

    # Looks like a Path
    elif isinstance(bgraph_str_or_path, Path) and Path.is_file(bgraph_str_or_path):
        bgraph_str = _read_bgraph_from_file(bgraph_str_or_path)

    # Could be string of path
    elif isinstance(bgraph_str_or_path, str) and ".bgraph" in bgraph_str_or_path:
        try:
            force_filepath_from_str = Path(bgraph_str_or_path)
            bgraph_str = _read_bgraph_from_file(force_filepath_from_str)
        except Exception as e:
            raise TQECError("Error trying to read what looks like a filepath") from e

    # Reject if input string remains empty
    if bgraph_str == "":
        raise TQECError("Error loading from BGRAPH. Empty BGRAPH string or incorrect filepath.")

    return bgraph_str


def _unpack_bgraph_str(bgraph_str, graph_name: str = "") -> tuple[float, str, list[str], list[str]]:
    """Extract key information from BGRAPH string.

    Args:
        bgraph_str: The input BGRAPH as a simple string.
        graph_name (optional): Name to give the blockgraph (overrides name in BGRAPH metadata).

    Returns:
        pipe_length: The length of pipes as declared in BGRAPH (or default value).
        graph_name: The name for the graph as declared in BGRAPH (or default value).
        cube_lines: Cubes in blockgraph.
        pipe_matches: Pipes in blockgraph.

    """
    try:
        # Get metadata using ReGex
        pipe_length_match = re.search(r"(?<=pipe_length; )(.*\b)", bgraph_str)
        pipe_length = float(pipe_length_match.group(0)) if pipe_length_match else 0.0
        if graph_name == "":
            graph_name_match = re.search(r"(?<=circuit_name; )(.*\b)", bgraph_str)
            graph_name = str(graph_name_match.group(0)) if graph_name_match else "circuit"

        # Split cubes and pipes sections
        cubes_start_index = bgraph_str.index("CUBES: index;x;y;z;kind;label;")
        pipes_start_index = bgraph_str.index("PIPES: src;tgt;kind;")
        cube_items = bgraph_str[cubes_start_index:pipes_start_index].splitlines()
        pipe_items = bgraph_str[pipes_start_index:].splitlines()

        cube_lines = [line for line in cube_items if line != "" and not line.startswith("CUBES:")]
        pipe_lines = [line for line in pipe_items if line != "" and not line.startswith("PIPES:")]

    except Exception as e:
        raise TQECError("Error unpacking BGRAPH.") from e

    return pipe_length, graph_name, cube_lines, pipe_lines


def _read_bgraph_from_file(filepath: Path) -> str:
    """Read :filetype:`.bgraph` and return its contents as string.

    Args:
        filepath: Path to external BGRAPH file.

    Returns:
        bgraph_str: The contents of the input file as a simple string.

    """
    with open(filepath) as f:
        bgraph_str = f.read()
    return bgraph_str


def _save_bgraph_to_file(filepath: str | Path, bgraph_lines: list[str]):
    """Write a :filetype:`.bgraph`.

    Args:
        filepath: Path to external BGRAPH file.
        bgraph_lines: The array containing all strings to be written into the file.

    """
    with open(filepath, "w") as f:
        f.writelines(bgraph_lines)
