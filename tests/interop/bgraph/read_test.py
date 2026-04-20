import io
from pathlib import Path

import pytest

from tqec.interop.bgraph.read import LoadFromBgraph, read_block_graph_from_bgraph
from tqec.utils.exceptions import TQECError


def test_bgraph_parse_method_rejects_invalid_inputs() -> None:
    # Init parser
    parser = LoadFromBgraph()

    # Ensure method does not run if called with incorrect optional parameters
    input_in_other_format = {0: "this is this", 1: "that is that"}
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        io_str = io.StringIO(
            "By participating in TQEC we agree and acknowledge that Adrien is a genius. =D"
        )
        _ = parser.parse(io_str=io_str)
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        _ = parser.parse(input_in_other_format=input_in_other_format)


@pytest.mark.parametrize("test_type", ["filepath", "raw_str"])
def test_bgraph_parse_method(test_type: str) -> None:
    # Init parser
    parser = LoadFromBgraph()

    # Expectations for all subsequent tests
    expected_cubes_selection = {
        4: {"position": (0, 0, 0), "kind": "ZXZ", "label": ""},
        3: {"position": (3, 0, 0), "kind": "XXZ", "label": ""},
        5: {"position": (0, 0, 3), "kind": "ZXX", "label": ""},
        6: {"position": (-3, 0, 0), "kind": "ZXZ", "label": ""},
        0: {"position": (6, 0, 0), "kind": "P", "label": "in_0"},
    }

    expected_pipes_selection = {
        (4, 3): {"kind": "OXZ"},
        (4, 5): {"kind": "ZXO"},
        (4, 6): {"kind": "OXZ"},
        (3, 0): {"kind": "OXZ"},
    }

    # Parse from file
    filepath = Path(__file__).parent.parent.parent.parent / "assets" / "cnots.bgraph"
    if test_type == "filepath":
        parsed_data = parser.parse(filepath=filepath)
    else:
        with open(filepath) as f:
            bgraph_str = f.read()
            f.close()
        parsed_data = parser.parse(raw_str=bgraph_str)

    assert parsed_data["name"] == "CNOTs"
    assert parsed_data["pipe_length"] == 2.0
    assert all(
        [
            parsed_data["cubes"][cube_id] == expected_cubes_selection[cube_id]
            for cube_id in [4, 3, 5, 6, 0]
        ]
    )
    assert all(
        [
            parsed_data["pipes"][pipe_id] == expected_pipes_selection[pipe_id]
            for pipe_id in [(4, 3), (4, 5), (4, 6), (3, 0)]
        ]
    )


@pytest.mark.parametrize("test_type", ["filepath", "raw_str"])
def test_read_block_graph_from_bgraph(test_type: str) -> None:
    expected_cubes_selection = [
        {"position": (0, 0, 0), "kind": "ZXZ", "label": ""},
        {"position": (1, 0, 0), "kind": "XXZ", "label": ""},
        {"position": (0, 0, 1), "kind": "ZXX", "label": ""},
        {"position": (-1, 0, 0), "kind": "ZXZ", "label": ""},
        {"position": (2, 0, 0), "kind": "PORT", "label": "in_0"},
    ]

    filepath = Path(__file__).parent.parent.parent.parent / "assets" / "cnots.bgraph"
    if test_type == "filepath":
        graph = read_block_graph_from_bgraph(filepath=filepath)
    else:
        with open(filepath) as f:
            bgraph_str = f.read()
            f.close()
        graph = read_block_graph_from_bgraph(bgraph_str=bgraph_str)

    assert all([cube in graph.to_dict()["cubes"] for cube in expected_cubes_selection])
