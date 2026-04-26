from pathlib import Path

import pytest

from tqec.interop.bgraph.read_write import load_bgraph, write_bgraph
from tqec.utils.exceptions import TQECError


@pytest.mark.parametrize(
    "input",
    [{0: "this is this", 1: "that is that"}, "common string", "BLOCKGRAPH but misformatted"],
)
def test_load_bgraph_rejects_invalid_input(input) -> None:
    with pytest.raises((AttributeError, AssertionError, TQECError)):
        _ = load_bgraph(input)


@pytest.mark.parametrize("test_type", ["filepath", "raw_str", "str_of_filepath"])
def test_bgraph_load_write(test_type: str) -> None:

    # Parse from assets file
    graph_name = "cnots"
    assets_folder = Path(__file__).parent.parent.parent.parent / "assets"
    filepath = assets_folder / f"{graph_name}.bgraph"

    # Load
    if test_type == "filepath":
        graph = load_bgraph(filepath)
    elif test_type == "str_of_filepath":
        graph = load_bgraph(str(filepath))
    else:
        with open(filepath) as f:
            bgraph_str = f.read()
            f.close()
        graph = load_bgraph(bgraph_str)

    # Write to string
    bgraph_out_str = write_bgraph(
        graph,
        pipe_length=2.0,
        graph_name=graph_name,
    )

    # Re-load and compare
    # String comparison not possible: IDs can change if source/output not by/from same tool
    graph_re = load_bgraph(bgraph_out_str)
    assert graph == graph_re
