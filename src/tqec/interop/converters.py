"""File-level converters between DAE and BGRAPH formats.

Both functions operate on file paths only; BlockGraph is an internal implementation
detail and does not appear in any signature. Could be made more efficient by manipulating text files directly
without creating ``BlockGraph`` objects.
"""

from pathlib import Path

from tqec.interop.bgraph import read_bgraph, write_bgraph
from tqec.interop.collada import (
    read_block_graph_from_dae_file,
    write_block_graph_to_dae_file,
)


def dae_to_bgraph(dae_path: Path | str, bgraph_path: Path | str, graph_name: str = "") -> None:
    """Convert a Collada DAE file to a BGRAPH file.

    Args:
        dae_path: Path to the input ``.dae`` file.
        bgraph_path: Path to the output ``.bgraph`` file.
        graph_name: Optional name to embed in the BGRAPH metadata. Defaults to the graph name
            found in the DAE scene, or an empty string if none is present.

    """
    _graph = read_block_graph_from_dae_file(Path(dae_path))
    write_bgraph(_graph, filepath=Path(bgraph_path), graph_name=graph_name)


def bgraph_to_dae(
    bgraph_path: Path | str,
    dae_path: Path | str,
    pipe_length: float = 2.0,
) -> None:
    """Convert a BGRAPH file to a Collada DAE file.

    Args:
        bgraph_path: Path to the input ``.bgraph`` file.
        dae_path: Path to the output ``.dae`` file.
        pipe_length: Length of the pipes in the COLLADA model. Default is 2.0.

    """
    _graph = read_bgraph(Path(bgraph_path))
    write_block_graph_to_dae_file(_graph, Path(dae_path), pipe_length=pipe_length)
