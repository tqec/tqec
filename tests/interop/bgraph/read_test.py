import io
from pathlib import Path

import pytest

from tqec.interop.bgraph.read import LoadFromBgraphFile
from tqec.utils.exceptions import TQECError


def test_bgraph_parse_method() -> None:
    # Init parser
    parser = LoadFromBgraphFile()

    # Ensure method does not run if called with incorrect optional parameters
    input_in_other_format = {0: "this is this", 1: "that is that"}
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        io_str = io.StringIO(
            "By participating in TQEC we agree and acknowledge that Adrien is a genius. =D"
        )
        parsed_data = parser.parse(io_str=io_str)
    with pytest.raises(TQECError, match=r".* method is currently only for `.bgraph` .*"):
        parsed_data = parser.parse(input_in_other_format=input_in_other_format)

    # Ensure results match expectations when running from filepath
    filepath = Path(__file__).parent.parent.parent.parent / "assets" / "cnots.bgraph"

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

    parsed_data = parser.parse(filepath=filepath)

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
