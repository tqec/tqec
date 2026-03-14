"""Read block graphs contained in a lattice surgery (LS) `.bgraph` file."""

from pathlib import Path

from tqec.computation.block_graph import BlockGraph
from tqec.computation.cube import YHalfCube
from tqec.interop.shared import int_position_before_scale, offset_y_cube_position
from tqec.utils.position import FloatPosition3D


def read_block_graph_from_bgraph_file(
    filepath: str | Path, graph_name: str = "", pipe_length: float = 2.0
) -> BlockGraph:
    """Read a .bgraph file and construct a :class:`.BlockGraph` from it.

    Args:
        filepath: The input `.bgraph` file path.
        graph_name: The name of the block graph. Default is an empty string.
        pipe_length: The length of pipes used by the source LS software.

    Returns:
        The constructed :py:class:`~tqec.computation.block_graph.BlockGraph` object.

    Raises:
        TQECError: If the COLLADA model cannot be parsed and converted to a block graph.

    """
    # Read file
    with open(filepath) as f:
        lines = f.readlines()
        f.close()

    # Parse cubes and pipes to respective dictionaries
    parsed_cubes: dict[int, dict[str, FloatPosition3D | str]] = {}
    parsed_pipes: dict[tuple[int, int], dict[str, str]] = {}

    parse_mode = None
    for line in lines:
        # Could be done with ReGeX using the following patterns:
        # - [catch first] PIPE LEN: (?<=pipe_length; )(.*\b)
        # - [catch first] GRAPH NAME: (?<=circuit_name; )(.*\b)
        # - [catch all] CUBE ENTRY (?<=\n)(\-*\d*;){3,}.*
        # - [catch all] PIPE ENTRY (?<=\n)(\d*;){2}\w{3};

        # But no one likes ReGex. =D
        # And seems premature to determine exact pattern matches at this point.
        # Maybe leave comment here until approach settles.

        # Look for flag to change from CUBEs to PIPEs mode
        if line.startswith("METADATA: "):
            parse_mode = "meta"
            continue
        if line.startswith("PIPES: "):
            parse_mode = "pipes"
            continue
        if line.startswith("CUBES: "):
            parse_mode = "cubes"
            continue
        if line.startswith("PIPES: "):
            parse_mode = "pipes"
            continue

        # Circuit name
        if parse_mode == "meta":
            try:
                if line.startswith("pipe_length: "):
                    _, pipe_length = line.strip().split(";")[:-1]
                    pipe_length = float(pipe_length)
                if line.startswith("circuit_name: "):
                    _, graph_name = line.strip().split(";")[:-1]
            except (ValueError, TypeError, IndexError, KeyError):
                raise ValueError("Error reading line (metadata) from `.bgraph` file.")

        # Cubes
        if parse_mode == "cubes" and line[0].isnumeric():
            try:
                cube_id, x, y, z, cube_kind, label = line.strip().split(";")[:-1]
                parsed_cubes[int(cube_id)] = {
                    "translation": FloatPosition3D(int(x), int(y), int(z)),
                    "kind": cube_kind.upper() if cube_kind.upper() != "OOO" else "P",
                    "label": label,
                }
            except (ValueError, TypeError, IndexError, KeyError):
                raise ValueError("Error reading line (cube) from `.bgraph` file.")

        # Pipes
        if parse_mode == "pipes" and line[0].isnumeric():
            try:
                src_id, tgt_id, pipe_kind = line.strip().split(";")[:-1]
                parsed_pipes[(int(src_id), int(tgt_id))] = {"kind": pipe_kind.upper()}
            except (ValueError, TypeError, IndexError, KeyError):
                raise ValueError("Error reading line (pipe) from `.bgraph` file.")

    # Construct blockgraph
    # Create graph
    graph = BlockGraph(graph_name)

    # Create dictionary to relate IDs in source file and IDs in blockgraph
    # It is NOT always the case that a .bgraph will have sequential or even numeric IDs.
    cube_id_conversions = {}

    # Add cubes
    i = 0
    for cube_id, cube_info in parsed_cubes.items():
        pos, cube_kind, label = cube_info.values()
        cube_id_conversions[cube_id] = i
        if isinstance(cube_kind, YHalfCube):
            graph.add_cube(
                int_position_before_scale(offset_y_cube_position(pos, pipe_length), pipe_length),
                cube_kind,
                label,
            )
        else:
            graph.add_cube(int_position_before_scale(pos, pipe_length), cube_kind, label)
        i += 1

    # Add pipes
    for src_id, tgt_id in parsed_pipes.keys():
        graph_src_id = cube_id_conversions[src_id]
        graph_tgt_id = cube_id_conversions[tgt_id]
        graph.add_pipe(graph.cubes[graph_src_id].position, graph.cubes[graph_tgt_id].position)

    return graph


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
    EXAMPLE_FOLDER = Path(__file__).parent
    TQEC_FOLDER = EXAMPLE_FOLDER.parent.parent.parent.parent
    ASSETS_FOLDER = TQEC_FOLDER / "assets"
    filepath = ASSETS_FOLDER / "cnots.bgraph"

    # Create graph
    graph_name = "CNOTs"
    graph = read_block_graph_from_bgraph_file(filepath, graph_name=graph_name)

    # Visualise graph
    write_to_html(graph_name, graph.view_as_html())
