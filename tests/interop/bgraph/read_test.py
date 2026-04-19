from pathlib import Path

import pytest

from tqec.interop.bgraph.read import LoadFromBgraphFile
from tqec.utils.exceptions import TQECError


def test_bgraph_parse_method() -> None:
    # Init parser
    parser = LoadFromBgraphFile()

    # Ensure method does not run if called with incorrect optional parameters
    io_str = "By participating in TQEC we all agree and acknowledge that Adrien is a genius. =D"
    input_in_other_format = {0: "this is this", 1: "that is that"}
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        parsed_data = parser.parse(io_str=io_str)
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        parsed_data = parser.parse(input_in_other_format=input_in_other_format)

    # Ensure results match expectations when running from filepath
    filepath = Path(__file__).parent.parent.parent.parent / "assets" / "cnots.bgraph"

    expected_cubes_selection = [
        {"position": (0, 0, 0), "kind": "ZXZ", "label": ""},
        {"position": (1, 0, 0), "kind": "XXZ", "label": ""},
        {"position": (0, 0, 1), "kind": "ZXX", "label": ""},
        {"position": (-1, 0, 0), "kind": "ZXZ", "label": ""},
        {"position": (2, 0, 0), "kind": "P", "label": "in_0"},
    ]

    expected_pipes_selection = [
        {"u": (0, 0, 0), "v": (1, 0, 0), "kind": "OXZ"},
        {"u": (0, 0, 0), "v": (0, 0, 1), "kind": "ZXO"},
        {"u": (0, 0, 0), "v": (-1, 0, 0), "kind": "OXZ"},
        {"u": (1, 0, 0), "v": (2, 0, 0), "kind": "OXZ"},
        {"u": (1, 0, 0), "v": (1, 1, 0), "kind": "XOZ"},
    ]

    parsed_data = parser.parse(filepath=filepath)
    assert parsed_data["name"] == "CNOTs"
    assert all([cube in parsed_data["cubes"] for cube in expected_cubes_selection])
    assert all([cube in parsed_data["pipes"] for cube in expected_pipes_selection])
